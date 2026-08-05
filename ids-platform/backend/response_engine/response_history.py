"""
Domain-facing wrapper around ResponseRepository - response_service.py calls
this rather than touching backend.database.repositories.responses directly,
mirroring how alert_service.py separates domain logic from raw repository
calls.
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from backend.database.models import ResponseHistory
from backend.database.repositories.responses import ResponseRepository
from backend.response_engine.response_registry import ActionResult
from backend.utils.logger import get_logger

logger = get_logger(__name__)


def record_result(
    db: Session,
    response_group_id: str,
    alert_id: str,
    result: ActionResult,
    mode: str,
    operator: str,
) -> ResponseHistory:
    row = ResponseHistory(
        id=str(uuid.uuid4()),
        response_group_id=response_group_id,
        alert_id=alert_id,
        action=result.action,
        status=result.status,
        message=result.message,
        execution_time_ms=result.execution_time_ms,
        operator=operator,
        mode=mode,
        rollback_available=result.rollback_available,
        rolled_back=False,
        metadata_json=result.metadata,
    )
    return ResponseRepository(db).create(row)


def new_group_id() -> str:
    return str(uuid.uuid4())
