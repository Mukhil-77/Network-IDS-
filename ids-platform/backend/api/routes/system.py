"""
GET /system/health

Distinct from Milestone 4's GET /health (which stays untouched): this
version additionally queries alert volume from the database and persists a
SystemHealth snapshot row on every call, giving the SOC a queryable health
history rather than only a point-in-time check.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends

from sqlalchemy.orm import Session

from backend.api.schemas import SystemHealthResponse, SystemStatsResponse
from backend.database.connection import get_db
from backend.database.models import SystemHealth
from backend.database.repositories.alerts import AlertRepository
from backend.services.prediction_service import prediction_service
from backend.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.get("/health", response_model=SystemHealthResponse, summary="Extended, DB-backed system health (persists a snapshot)")
async def system_health(db: Session = Depends(get_db)) -> SystemHealthResponse:
    model_loaded = prediction_service.is_model_loaded()
    model_version = None
    if model_loaded:
        try:
            model_version = prediction_service.get_model_metadata().model_version_dir
        except Exception:  # noqa: BLE001 - health reporting must never itself fail
            model_version = None

    since = datetime.now(timezone.utc) - timedelta(minutes=1)
    alerts_last_minute = AlertRepository(db).count_since(since)

    snapshot = SystemHealth(
        status="healthy" if model_loaded else "degraded",
        model_status="loaded" if model_loaded else "unavailable",
        model_version=model_version,
        active_flows=0,  # no process-wide FlowManager singleton exists yet - see Milestone 6 docs' "Deferred" note
        alerts_last_minute=alerts_last_minute,
    )
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)

    return SystemHealthResponse(
        status=snapshot.status,
        model_status=snapshot.model_status,
        model_version=snapshot.model_version,
        active_flows=snapshot.active_flows,
        alerts_last_minute=snapshot.alerts_last_minute,
        timestamp=snapshot.timestamp,
    )


@router.get("/stats", response_model=SystemStatsResponse, summary="Live OS telemetry: CPU, memory, disk, network, GPU (task-manager view)")
async def system_stats() -> SystemStatsResponse:
    from backend.services.system_metrics import collect_system_stats

    stats = collect_system_stats()
    return SystemStatsResponse(**stats)