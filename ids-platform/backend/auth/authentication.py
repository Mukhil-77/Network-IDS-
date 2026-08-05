"""
Core authentication flows: login (verify + issue tokens + create session),
refresh (validate + rotate), logout (revoke), and one-time default-data
seeding. Kept separate from auth/routes.py so this logic is directly unit-
testable without going through HTTP.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.auth import audit
from backend.auth.jwt_manager import (
    REFRESH_TOKEN_TYPE,
    ExpiredTokenError,
    InvalidTokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from backend.auth.models import Permission, Role, User, UserSession
from backend.auth.password import hash_password, verify_password
from backend.auth.permissions import DEFAULT_ROLE_DESCRIPTIONS, DEFAULT_ROLE_PERMISSIONS, PERMISSION_CATALOG
from backend.core.config import get_settings
from backend.utils.logger import get_logger

logger = get_logger(__name__)


def _as_aware_utc(value: datetime) -> datetime:
    """SQLite doesn't reliably preserve timezone-awareness on DateTime columns through a round trip (see the call site in refresh_access_token) - treat a naive value as already-UTC rather than raising."""
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


class AuthenticationError(Exception):
    """Wrong username/password, inactive account, or an invalid/expired/reused token."""


def _hash_token(token: str) -> str:
    """
    SHA-256, not bcrypt: refresh tokens are already high-entropy random
    JWTs (unlike user passwords, which are low-entropy and need a slow,
    salted hash to resist offline brute-forcing) - a fast cryptographic
    hash is the right tool here, and using bcrypt on a >72-byte JWT would
    silently truncate it (see password.py's docstring).
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------
# Seeding (called once at startup - see main.py)
# --------------------------------------------------------------------------

def seed_default_data(db: Session) -> None:
    """
    Incrementally idempotent: adds any permission from PERMISSION_CATALOG
    that doesn't exist yet (by name), grants any of DEFAULT_ROLE_PERMISSIONS
    that a default role doesn't already have (by name), and creates the
    default admin user only if no user exists at all. Never removes or
    overwrites anything an operator has since changed - only ever adds what's
    missing, so a later milestone's new permissions reach an already-seeded
    database on its next startup instead of being silently skipped forever.
    """
    existing_permissions = {p.name: p for p in db.execute(select(Permission)).scalars().all()}
    newly_added_permissions = 0
    for name, description in PERMISSION_CATALOG.items():
        if name not in existing_permissions:
            permission = Permission(name=name, description=description)
            db.add(permission)
            db.flush()
            existing_permissions[name] = permission
            newly_added_permissions += 1
    if newly_added_permissions:
        logger.info("Seeded %d new permission(s)", newly_added_permissions)

    existing_roles = {r.name: r for r in db.execute(select(Role)).scalars().all()}
    for role_name, permission_names in DEFAULT_ROLE_PERMISSIONS.items():
        role = existing_roles.get(role_name)
        if role is None:
            role = Role(name=role_name, description=DEFAULT_ROLE_DESCRIPTIONS.get(role_name, ""))
            db.add(role)
            db.flush()
            existing_roles[role_name] = role
            logger.info("Seeded new default role: %s", role_name)

        current_permission_names = {p.name for p in role.permissions}
        missing = permission_names - current_permission_names
        if missing:
            role.permissions = list(role.permissions) + [existing_permissions[p] for p in missing if p in existing_permissions]
            logger.info("Granted %d new default permission(s) to role '%s': %s", len(missing), role_name, sorted(missing))

    if db.execute(select(User)).first() is None:
        settings = get_settings()
        admin_role = db.execute(select(Role).where(Role.name == "Admin")).scalars().first()
        if admin_role is not None:
            db.add(User(
                username=settings.DEFAULT_ADMIN_USERNAME,
                email=settings.DEFAULT_ADMIN_EMAIL,
                hashed_password=hash_password(settings.DEFAULT_ADMIN_PASSWORD),
                role_id=admin_role.id,
            ))
            db.flush()
            logger.warning(
                "No users existed - seeded a default admin account (username=%s). "
                "CHANGE THIS PASSWORD IMMEDIATELY in any real deployment.",
                settings.DEFAULT_ADMIN_USERNAME,
            )


# --------------------------------------------------------------------------
# Login / logout / refresh
# --------------------------------------------------------------------------

def authenticate_user(db: Session, username: str, password: str) -> User:
    """Raises AuthenticationError (without distinguishing "no such user" from "wrong password" in the message - avoids username enumeration)."""
    user = db.execute(select(User).where(User.username == username)).scalars().first()
    if user is None or not verify_password(password, user.hashed_password):
        raise AuthenticationError("Invalid username or password")
    if not user.is_active:
        raise AuthenticationError("This account has been deactivated")
    return user


def login(db: Session, username: str, password: str, ip_address: Optional[str], user_agent: Optional[str]) -> tuple[str, str, int]:
    """
    Returns (access_token, refresh_token, expires_in_seconds).
    Raises AuthenticationError on bad credentials (also audit-logged as a failure).
    """
    try:
        user = authenticate_user(db, username, password)
    except AuthenticationError:
        audit.log_event(db, actor=username, action=audit.LOGIN_FAILED, ip_address=ip_address, status="failed")
        raise

    access_token = create_access_token(user.id, user.username, user.role.name)
    refresh_token, jti, expires_at = create_refresh_token(user.id, user.username, user.role.name)

    db.add(UserSession(
        id=jti, user_id=user.id, refresh_token_hash=_hash_token(refresh_token),
        expires_at=expires_at, user_agent=user_agent, ip_address=ip_address,
    ))
    user.last_login_at = datetime.now(timezone.utc)

    audit.log_event(db, actor=user.username, action=audit.LOGIN_SUCCESS, role=user.role.name, ip_address=ip_address)

    settings = get_settings()
    return access_token, refresh_token, settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60


def refresh_access_token(db: Session, refresh_token: str, ip_address: Optional[str], user_agent: Optional[str]) -> tuple[str, str, int]:
    """
    Validates + ROTATES the refresh token (old session revoked, new one
    issued) - see jwt_manager.py's docstring for why rotation matters.
    Raises AuthenticationError if the token is invalid, expired, revoked,
    or doesn't match any stored session (e.g. already rotated once before -
    a sign of possible token theft).
    """
    try:
        payload = decode_token(refresh_token, expected_type=REFRESH_TOKEN_TYPE)
    except (InvalidTokenError, ExpiredTokenError) as exc:
        raise AuthenticationError(str(exc)) from exc

    session = db.get(UserSession, payload.jti)
    if session is None or session.revoked or _hash_token(refresh_token) != session.refresh_token_hash:
        raise AuthenticationError("Refresh token is invalid or has already been used")
    if _as_aware_utc(session.expires_at) < datetime.now(timezone.utc):
        raise AuthenticationError("Refresh token has expired")

    user = db.get(User, session.user_id)
    if user is None or not user.is_active:
        raise AuthenticationError("Account is no longer active")

    session.revoked = True  # rotation: this refresh token can never be used again

    access_token = create_access_token(user.id, user.username, user.role.name)
    new_refresh_token, new_jti, new_expires_at = create_refresh_token(user.id, user.username, user.role.name)
    db.add(UserSession(
        id=new_jti, user_id=user.id, refresh_token_hash=_hash_token(new_refresh_token),
        expires_at=new_expires_at, user_agent=user_agent, ip_address=ip_address,
    ))

    audit.log_event(db, actor=user.username, action=audit.TOKEN_REFRESHED, role=user.role.name, ip_address=ip_address)

    settings = get_settings()
    return access_token, new_refresh_token, settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60


def logout(db: Session, refresh_token: str, actor_username: str, ip_address: Optional[str]) -> None:
    """Revokes the session tied to this refresh token. Silently no-ops if the token is already invalid/unknown - logout should never itself fail loudly."""
    try:
        payload = decode_token(refresh_token, expected_type=REFRESH_TOKEN_TYPE)
        session = db.get(UserSession, payload.jti)
        if session is not None:
            session.revoked = True
    except (InvalidTokenError, ExpiredTokenError):
        pass

    audit.log_event(db, actor=actor_username, action=audit.LOGOUT, ip_address=ip_address)
