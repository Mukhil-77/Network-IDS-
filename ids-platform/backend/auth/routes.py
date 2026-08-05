"""
POST /auth/login, /auth/logout, /auth/refresh, /auth/register,
GET /auth/me, PUT /auth/profile, GET /users, GET /roles, GET /audit,
plus the password-reset placeholder pair.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.auth import audit, authentication
from backend.auth.authentication import AuthenticationError
from backend.auth.dependencies import get_client_ip, get_current_user, require_permission
from backend.auth.jwt_manager import ExpiredTokenError, InvalidTokenError, _encode, decode_token
from backend.auth.models import Role, User
from backend.auth.password import hash_password, verify_password
from backend.auth.schemas import (
    AuditLogResponse,
    ForgotPasswordRequest,
    LoginRequest,
    PaginatedAuditLog,
    ProfileUpdateRequest,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    RoleResponse,
    TokenResponse,
    UserResponse,
)
from backend.database.connection import get_db
from backend.database.models import AuditLog
from backend.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()

RESET_TOKEN_TYPE = "password_reset"


@router.post("/auth/login", response_model=TokenResponse, summary="Log in with username and password")
async def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)) -> TokenResponse:
    try:
        access_token, refresh_token, expires_in = authentication.login(
            db, payload.username, payload.password, get_client_ip(request), request.headers.get("User-Agent"),
        )
    except AuthenticationError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    return TokenResponse(access_token=access_token, refresh_token=refresh_token, expires_in=expires_in)


@router.post("/auth/refresh", response_model=TokenResponse, summary="Exchange a refresh token for a new access token (rotates the refresh token)")
async def refresh(payload: RefreshRequest, request: Request, db: Session = Depends(get_db)) -> TokenResponse:
    try:
        access_token, refresh_token, expires_in = authentication.refresh_access_token(
            db, payload.refresh_token, get_client_ip(request), request.headers.get("User-Agent"),
        )
    except AuthenticationError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    return TokenResponse(access_token=access_token, refresh_token=refresh_token, expires_in=expires_in)


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT, summary="Revoke the current session's refresh token")
async def logout(
    payload: RefreshRequest, request: Request,
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
) -> None:
    authentication.logout(db, payload.refresh_token, user.username, get_client_ip(request))


@router.post("/auth/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED, summary="Create a new user account")
async def register(payload: RegisterRequest, request: Request, db: Session = Depends(get_db)) -> UserResponse:
    if db.execute(select(User).where(User.username == payload.username)).first() is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already taken")
    if db.execute(select(User).where(User.email == payload.email)).first() is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    role = db.execute(select(Role).where(Role.name == payload.role)).scalars().first()
    if role is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown role '{payload.role}'")

    user = User(username=payload.username, email=payload.email, hashed_password=hash_password(payload.password), role_id=role.id)
    db.add(user)
    db.flush()

    audit.log_event(db, actor=user.username, action=audit.REGISTER, role=role.name, ip_address=get_client_ip(request))

    return UserResponse(id=user.id, username=user.username, email=user.email, role=role.name, is_active=user.is_active, created_at=user.created_at)


@router.get("/auth/me", response_model=UserResponse, summary="Current user's profile")
async def me(user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse(
        id=user.id, username=user.username, email=user.email, role=user.role.name,
        is_active=user.is_active, created_at=user.created_at, last_login_at=user.last_login_at,
    )


@router.put("/auth/profile", response_model=UserResponse, summary="Update email and/or password")
async def update_profile(
    payload: ProfileUpdateRequest, request: Request,
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
) -> UserResponse:
    if payload.new_password is not None:
        if payload.current_password is None or not verify_password(payload.current_password, user.hashed_password):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")
        user.hashed_password = hash_password(payload.new_password)
        audit.log_event(db, actor=user.username, action=audit.PASSWORD_CHANGED, role=user.role.name, ip_address=get_client_ip(request))

    if payload.email is not None:
        user.email = payload.email
        audit.log_event(db, actor=user.username, action=audit.PROFILE_UPDATED, role=user.role.name, ip_address=get_client_ip(request), details={"email": payload.email})

    return UserResponse(id=user.id, username=user.username, email=user.email, role=user.role.name, is_active=user.is_active, created_at=user.created_at, last_login_at=user.last_login_at)


@router.post("/auth/forgot-password", status_code=status.HTTP_202_ACCEPTED, summary="Request a password reset (placeholder)")
async def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)) -> dict:
    """
    Placeholder, as specced: issues a real, short-lived reset token if the
    email matches an account, but doesn't actually deliver it anywhere
    (no email service is wired up in this milestone - the token is only
    logged server-side). Always returns the same generic response whether
    or not the email exists, so this endpoint can't be used to enumerate
    registered accounts.
    """
    user = db.execute(select(User).where(User.email == payload.email)).scalars().first()
    if user is not None:
        reset_token, _ = _issue_reset_token(user)
        logger.info("[PLACEHOLDER] Password reset requested for %s - token (would be emailed): %s", user.email, reset_token)

    return {"message": "If that email is registered, a reset link has been sent."}


@router.post("/auth/reset-password", status_code=status.HTTP_204_NO_CONTENT, summary="Complete a password reset (placeholder)")
async def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)) -> None:
    try:
        token_payload = decode_token(payload.reset_token, expected_type=RESET_TOKEN_TYPE)
    except (InvalidTokenError, ExpiredTokenError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token") from exc

    user = db.get(User, token_payload.sub)
    if user is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token")

    user.hashed_password = hash_password(payload.new_password)
    audit.log_event(db, actor=user.username, action=audit.PASSWORD_CHANGED, role=user.role.name, details={"method": "reset"})


def _issue_reset_token(user: User) -> tuple[str, datetime]:
    expires_delta = timedelta(minutes=30)
    token, _ = _encode(user.id, user.username, user.role.name, RESET_TOKEN_TYPE, expires_delta)
    return token, datetime.now(timezone.utc) + expires_delta


@router.get("/users", response_model=list[UserResponse], summary="List user accounts")
async def list_users(db: Session = Depends(get_db), _: User = Depends(require_permission("users:read"))) -> list[UserResponse]:
    users = db.execute(select(User)).scalars().all()
    return [
        UserResponse(id=u.id, username=u.username, email=u.email, role=u.role.name, is_active=u.is_active, created_at=u.created_at, last_login_at=u.last_login_at)
        for u in users
    ]


@router.get("/roles", response_model=list[RoleResponse], summary="List roles and their permissions")
async def list_roles(db: Session = Depends(get_db), _: User = Depends(require_permission("roles:read"))) -> list[RoleResponse]:
    roles = db.execute(select(Role)).scalars().all()
    return [RoleResponse(id=r.id, name=r.name, description=r.description, permissions=[p.name for p in r.permissions]) for r in roles]


@router.get("/audit", response_model=PaginatedAuditLog, summary="List audit log entries")
async def list_audit_log(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("audit:read")),
    actor: str | None = Query(None),
    action: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
) -> PaginatedAuditLog:
    stmt = select(AuditLog)
    if actor is not None:
        stmt = stmt.where(AuditLog.actor == actor)
    if action is not None:
        stmt = stmt.where(AuditLog.action == action)

    total = len(db.execute(stmt).all())
    stmt = stmt.order_by(AuditLog.timestamp.desc()).offset((page - 1) * page_size).limit(page_size)
    items = list(db.execute(stmt).scalars().all())

    return PaginatedAuditLog(items=[AuditLogResponse.model_validate(i) for i in items], total=total, page=page, page_size=page_size)
