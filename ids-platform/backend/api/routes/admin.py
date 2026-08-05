"""
Admin data-management endpoints (Settings page "Danger Zone").

    POST /admin/data/clear    Delete operational data by scope (alerts, flows,
                              responses, incidents, statistics, audit, threat intel)
    POST /admin/models/reset  Delete every trained model version + its DB records

Both are destructive by design, gated behind the `settings:write` permission
(which only the Admin role carries by default - see auth/permissions.py), and
each returns an explicit summary of what was removed so the frontend can show
exactly what happened.

Deletion order matters: ResponseHistory and Incident rows reference Alert rows,
which reference FlowHistory rows - children are always deleted first.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import delete
from sqlalchemy.orm import Session

from backend.auth.dependencies import require_permission
from backend.auth.models import User
from backend.database.connection import get_db
from backend.database.models import (
    Alert,
    AttackStatistics,
    AuditLog,
    BlockedIP,
    FlowHistory,
    Incident,
    ModelMetadataRecord,
    PacketStatistics,
    ResponseHistory,
    SystemHealth,
    ThreatIndicator,
)
from backend.services.prediction_service import prediction_service
from backend.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/admin", tags=["Admin"])

# scope name -> (ORM model, human-readable label). Every model here is a
# leaf in the FK graph or already ordered child-first (ResponseHistory and
# Incident precede Alert; Alert precedes FlowHistory).
CLEAR_SCOPES: dict[str, tuple[type, str]] = {
    "responses": (ResponseHistory, "response history"),
    "incidents": (Incident, "incidents"),
    "alerts": (Alert, "alerts"),
    "flows": (FlowHistory, "flows"),
    "statistics": (AttackStatistics, "attack statistics"),
    "system_health": (SystemHealth, "system health snapshots"),
    "packet_stats": (PacketStatistics, "packet statistics"),
    "audit": (AuditLog, "audit log"),
    "threat_intel": (ThreatIndicator, "threat indicators"),
    "blocked_ips": (BlockedIP, "blocked IPs"),
}


class ClearDataRequest(BaseModel):
    scopes: list[str] = Field(
        default_factory=list,
        description="Subset of the clearable scopes; empty list means ALL scopes.",
    )


class ClearDataResponse(BaseModel):
    deleted: dict[str, int]


class ResetModelsResponse(BaseModel):
    removed_versions: list[str]
    model_metadata_rows_deleted: int


@router.post("/data/clear", response_model=ClearDataResponse, summary="Delete operational data by scope (alerts, flows, statistics, audit, ...)")
async def clear_data(
    payload: ClearDataRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("settings:write")),
) -> ClearDataResponse:
    scopes = payload.scopes or list(CLEAR_SCOPES.keys())

    unknown = [s for s in scopes if s not in CLEAR_SCOPES]
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown clear scope(s): {', '.join(unknown)}",
        )

    deleted: dict[str, int] = {}
    for scope in scopes:
        model, label = CLEAR_SCOPES[scope]
        result = db.execute(delete(model))
        count = result.rowcount or 0
        deleted[scope] = count
        logger.info("Cleared %d %s row(s) (scope='%s', actor=%s)", count, label, scope, user.username)

    db.commit()
    return ClearDataResponse(deleted=deleted)


@router.post("/models/reset", response_model=ResetModelsResponse, summary="Delete every trained model version and its database records")
async def reset_models(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("settings:write")),
) -> ResetModelsResponse:
    removed_versions = prediction_service.reset_models()
    metadata_deleted = db.execute(delete(ModelMetadataRecord)).rowcount or 0
    db.commit()
    logger.info(
        "Reset models (actor=%s): removed versions=%s, metadata rows=%d",
        user.username, removed_versions, metadata_deleted,
    )
    return ResetModelsResponse(
        removed_versions=removed_versions,
        model_metadata_rows_deleted=metadata_deleted,
    )
