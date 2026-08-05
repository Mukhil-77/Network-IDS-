"""
Auth data-access layer: user, session and audit-log DB operations.

Centralizes every SQLAlchemy query the auth package makes so the route
handlers in auth/routes.py stay thin and the repository pattern matches the
rest of the codebase (backend/database/repositories/*).

Each repository takes a SQLAlchemy ``Session`` in its constructor and
operates on the models defined in backend/auth/models.py (User, Role,
UserSession) and backend/database/models.py (AuditLog).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.auth.models import Role, User, UserSession
from backend.database.models import AuditLog


class UserRepository:
    """CRUD for users (backend/auth/models.py)."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, user_id: str) -> Optional[User]:
        return self.db.get(User, user_id)

    def get_by_username(self, username: str) -> Optional[User]:
        return self.db.execute(select(User).where(User.username == username)).scalars().first()

    def get_by_email(self, email: str) -> Optional[User]:
        return self.db.execute(select(User).where(User.email == email)).scalars().first()

    def list_all(self) -> list[User]:
        return list(self.db.execute(select(User).order_by(User.created_at)).scalars().all())

    def create(self, username: str, email: str, hashed_password: str, role: Role, *, is_active: bool = True) -> User:
        user = User(
            username=username,
            email=email,
            hashed_password=hashed_password,
            role_id=role.id,
            is_active=is_active,
        )
        self.db.add(user)
        self.db.flush()
        return user

    def update_role(self, user: User, role: Role) -> User:
        user.role_id = role.id
        return user

    def set_active(self, user: User, is_active: bool) -> User:
        user.is_active = is_active
        return user

    def touch_login(self, user: User) -> User:
        user.last_login_at = datetime.now(timezone.utc)
        return user


class SessionRepository:
    """Refresh-token session rows (backend/auth/models.py: UserSession)."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_token_hash(self, refresh_token_hash: str) -> Optional[UserSession]:
        return self.db.execute(
            select(UserSession).where(UserSession.refresh_token_hash == refresh_token_hash)
        ).scalars().first()

    def create(
        self,
        user_id: str,
        refresh_token_hash: str,
        expires_at: datetime,
        *,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> UserSession:
        session = UserSession(
            user_id=user_id,
            refresh_token_hash=refresh_token_hash,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self.db.add(session)
        self.db.flush()
        return session

    def revoke(self, session: UserSession) -> UserSession:
        session.revoked = True
        return session

    def list_active_for_user(self, user_id: str) -> list[UserSession]:
        return list(
            self.db.execute(
                select(UserSession)
                .where(UserSession.user_id == user_id, UserSession.revoked.is_(False))
                .order_by(UserSession.created_at.desc())
            ).scalars().all()
        )

    def delete_expired(self, now: Optional[datetime] = None) -> int:
        """Remove rows whose tokens have expired. Returns the number deleted."""
        now = now or datetime.now(timezone.utc)
        rows = list(self.db.execute(select(UserSession).where(UserSession.expires_at < now)).scalars().all())
        for row in rows:
            self.db.delete(row)
        return len(rows)


class AuditLogRepository:
    """Read/write for the audit log (backend/database/models.py: AuditLog)."""

    def __init__(self, db: Session):
        self.db = db

    def log(
        self,
        *,
        actor: str,
        action: str,
        target: Optional[str] = None,
        details: Optional[dict] = None,
        ip_address: Optional[str] = None,
        user_id: Optional[str] = None,
        role: Optional[str] = None,
        status: str = "success",
    ) -> AuditLog:
        entry = AuditLog(
            actor=actor,
            action=action,
            target=target,
            details=details,
            ip_address=ip_address,
            user_id=user_id,
            role=role,
            status=status,
        )
        self.db.add(entry)
        self.db.flush()
        return entry

    def list_entries(
        self,
        *,
        actor: Optional[str] = None,
        action: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[AuditLog]:
        stmt = select(AuditLog)
        if actor is not None:
            stmt = stmt.where(AuditLog.actor == actor)
        if action is not None:
            stmt = stmt.where(AuditLog.action == action)
        stmt = stmt.order_by(AuditLog.timestamp.desc()).offset(skip).limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    def delete_all(self) -> int:
        rows = list(self.db.execute(select(AuditLog)).scalars().all())
        for row in rows:
            self.db.delete(row)
        return len(rows)
