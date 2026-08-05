"""GET /statistics - the SOC dashboard summary."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from backend.auth.dependencies import require_permission
from backend.auth.models import User
from sqlalchemy.orm import Session

from backend.api.schemas import StatisticsResponse
from backend.database.connection import get_db
from backend.services.statistics_service import StatisticsService

router = APIRouter()
_service = StatisticsService()


@router.get("/statistics", response_model=StatisticsResponse, summary="Threat counts, breakdowns, and detection metrics")
async def get_statistics(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("statistics:read")),
    window_minutes: int = Query(60, ge=1, le=1440, description="Window for the threats-per-minute time series"),
) -> StatisticsResponse:
    summary = _service.get_summary(db, window_minutes=window_minutes)
    return StatisticsResponse(**summary)
