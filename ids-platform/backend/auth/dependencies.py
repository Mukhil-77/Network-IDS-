"""
FastAPI dependencies for protecting routes.

    Depends(get_current_user)                    - any valid access token
    Depends(require_permission("alerts:read"))    - valid token + that permission
    Depends(require_role("Admin"))                - valid token + one of these roles

Every protected route in backend/api/routes/*.py uses one of these three -
no route re-implements token parsing or permission checking.
"""

from __future__ import annotations

from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from backend.auth.authorization import has_permission, has_role
from backend.auth.jwt_manager import ACCESS_TOKEN_TYPE, ExpiredTokenError, InvalidTokenError, decode_token
from backend.auth.models import User
from backend.database.connection import get_db

# `auto_error=False` so a missing Authorization header produces our own
# 401 with a consistent error body (via exception_handlers.py) rather than
# FastAPI/Starlette's default plain-text 403.
_bearer_scheme = HTTPBearer(auto_error=False)


def get_client_ip(request: Request) -> Optional[str]:
    """Prefers X-Forwarded-For's first hop (reverse-proxy deployments) over the raw connection IP."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated", headers={"WWW-Authenticate": "Bearer"})

    try:
        payload = decode_token(credentials.credentials, expected_type=ACCESS_TOKEN_TYPE)
    except ExpiredTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired, please log in again", headers={"WWW-Authenticate": "Bearer"})
    except InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication token", headers={"WWW-Authenticate": "Bearer"})

    user = db.get(User, payload.sub)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account no longer active", headers={"WWW-Authenticate": "Bearer"})

    return user


def require_permission(permission: str):
    def _dependency(user: User = Depends(get_current_user)) -> User:
        if not has_permission(user, permission):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Requires permission: {permission}")
        return user
    return _dependency


def require_role(*role_names: str):
    def _dependency(user: User = Depends(get_current_user)) -> User:
        if not has_role(user, *role_names):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Requires role: {' or '.join(role_names)}")
        return user
    return _dependency
