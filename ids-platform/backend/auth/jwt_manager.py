"""
JWT encode/decode for access and refresh tokens.

Two token types, distinguished by a "type" claim (not by structure alone -
an access token and a refresh token look superficially similar, and
`decode_token()` deliberately checks `type` so an access token can never be
replayed where a refresh token is expected, or vice versa):

    Access token  - short-lived (ACCESS_TOKEN_EXPIRE_MINUTES, default 15m),
                    sent on every API request, never persisted server-side
                    (stateless - revocation isn't possible before expiry,
                    which is why it's kept short).
    Refresh token - longer-lived (REFRESH_TOKEN_EXPIRE_DAYS, default 7d),
                    its *hash* is persisted in UserSession (auth/models.py)
                    so it CAN be revoked (logout) and IS rotated on every
                    use (auth/authentication.py's refresh flow) - a stolen
                    refresh token that gets used by its rightful owner
                    after the thief already used it is detectable, because
                    the old one no longer matches any active session.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from pydantic import BaseModel

from backend.core.config import get_settings
from backend.utils.logger import get_logger

logger = get_logger(__name__)

ACCESS_TOKEN_TYPE = "access"
REFRESH_TOKEN_TYPE = "refresh"


class TokenPayload(BaseModel):
    sub: str  # user id
    username: str
    role: str
    type: str
    jti: str  # unique token id - lets a specific refresh token be matched to its UserSession row
    exp: int
    iat: int


class InvalidTokenError(Exception):
    pass


class ExpiredTokenError(InvalidTokenError):
    pass


def _encode(user_id: str, username: str, role: str, token_type: str, expires_delta: timedelta) -> tuple[str, str]:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    jti = str(uuid.uuid4())
    payload = {
        "sub": user_id, "username": username, "role": role, "type": token_type,
        "jti": jti, "iat": int(now.timestamp()), "exp": int((now + expires_delta).timestamp()),
    }
    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, jti


def create_access_token(user_id: str, username: str, role: str) -> str:
    settings = get_settings()
    token, _ = _encode(user_id, username, role, ACCESS_TOKEN_TYPE, timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    return token


def create_refresh_token(user_id: str, username: str, role: str) -> tuple[str, str, datetime]:
    """Returns (token, jti, expires_at) - the caller (authentication.py) persists a hash of `token` keyed by `jti` in UserSession."""
    settings = get_settings()
    expires_delta = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    token, jti = _encode(user_id, username, role, REFRESH_TOKEN_TYPE, expires_delta)
    expires_at = datetime.now(timezone.utc) + expires_delta
    return token, jti, expires_at


def decode_token(token: str, expected_type: Optional[str] = None) -> TokenPayload:
    """
    Raises:
        ExpiredTokenError: token's exp has passed.
        InvalidTokenError: signature invalid, malformed, or (if
            `expected_type` given) wrong token type.
    """
    settings = get_settings()
    try:
        raw = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise ExpiredTokenError("Token has expired") from exc
    except jwt.InvalidTokenError as exc:
        raise InvalidTokenError(f"Invalid token: {exc}") from exc

    try:
        payload = TokenPayload.model_validate(raw)
    except Exception as exc:  # noqa: BLE001 - malformed claims are an invalid token, not a 500
        raise InvalidTokenError(f"Malformed token payload: {exc}") from exc

    if expected_type is not None and payload.type != expected_type:
        raise InvalidTokenError(f"Expected a '{expected_type}' token, got '{payload.type}'")

    return payload
