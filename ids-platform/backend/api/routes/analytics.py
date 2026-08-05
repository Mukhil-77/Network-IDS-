"""GET /analytics, GET /analytics/trends."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.analytics.analytics_service import get_overview, get_trends
from backend.api.schemas import AnalyticsOverviewResponse, AnalyticsTrendsResponse
from backend.auth.dependencies import require_permission
from backend.auth.models import User
from backend.database.connection import get_db

router = APIRouter()


@router.get("/analytics", response_model=AnalyticsOverviewResponse, summary="Full analytics overview")
async def analytics_overview(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("analytics:read")),
    timeline_days: int = Query(30, ge=1, le=365),
) -> AnalyticsOverviewResponse:
    return AnalyticsOverviewResponse(**get_overview(db, timeline_days=timeline_days))


@router.get("/analytics/trends", response_model=AnalyticsTrendsResponse, summary="Attack timeline with a short-term forecast")
async def analytics_trends(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("analytics:read")),
    timeline_days: int = Query(30, ge=1, le=365),
    forecast_days: int = Query(7, ge=1, le=30),
) -> AnalyticsTrendsResponse:
    return AnalyticsTrendsResponse(**get_trends(db, timeline_days=timeline_days, forecast_days=forecast_days))
