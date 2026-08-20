"""
Writes to the existing (Milestone 6/8, now Milestone 9-extended) AuditLog
table - see database/models.py's AuditLog docstring. This module exists so
every auth-related call site logs consistently (same field mapping) rather
than constructing AuditLog rows by hand in five different places.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from backend.database.models import AuditLog
from backend.utils.logger import get_logger

logger = get_logger(__name__)

# Action name constants - used both when writing and when the GET /audit
# route's tests assert on them, so a typo can't silently create a new,
# unfiltered action name.
LOGIN_SUCCESS = "user_login"
LOGIN_FAILED = "user_login_failed"
LOGOUT = "user_logout"
TOKEN_REFRESHED = "token_refreshed"
REGISTER = "user_registered"
PASSWORD_CHANGED = "password_changed"
PROFILE_UPDATED = "profile_updated"
ROLE_CHANGED = "role_changed"
USER_CREATED = "user_created"
USER_DEACTIVATED = "user_deactivated"
USER_REACTIVATED = "user_reactivated"


def log_event(
    db: Session,
    *,
    actor: str,
    action: str,
    target: Optional[str] = None,
    role: Optional[str] = None,
    ip_address: Optional[str] = None,
    status: str = "success",
    details: Optional[dict] = None,
) -> AuditLog:
    entry = AuditLog(actor=actor, action=action, target=target, role=role, ip_address=ip_address, status=status, details=details)
    db.add(entry)
    db.flush()
    logger.info(
        "AUDIT actor=%s action=%s target=%s status=%s ip=%s",
        actor, action, target, status, ip_address,
    )
    return entry
