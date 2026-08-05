"""
GET /alerts, /alerts/{id}, /alerts/latest.

All query logic lives in AlertRepository (backend/database/repositories/alerts.py) -
this module only translates query params into an AlertFilters/pagination
call and reshapes the ORM rows into AlertResponse.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.auth.dependencies import require_permission
from backend.auth.models import User
from sqlalchemy.orm import Session

from backend.api.schemas import AlertResponse, PaginatedAlertsResponse
from backend.database.connection import get_db
from backend.database.repositories.alerts import AlertFilters, AlertRepository

router = APIRouter()


@router.get("/alerts", response_model=PaginatedAlertsResponse, summary="List alerts with filtering, pagination, and sorting")
async def list_alerts(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("alerts:read")),
    start_date: Optional[datetime] = Query(None, description="Only alerts at or after this timestamp"),
    end_date: Optional[datetime] = Query(None, description="Only alerts at or before this timestamp"),
    attack_type: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    source_ip: Optional[str] = Query(None),
    destination_ip: Optional[str] = Query(None),
    min_confidence: Optional[float] = Query(None, ge=0.0, le=100.0),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    sort_by: str = Query("timestamp", pattern="^(timestamp|confidence|severity)$"),
    sort_desc: bool = Query(True),
) -> PaginatedAlertsResponse:
    filters = AlertFilters(
        start_date=start_date, end_date=end_date, attack_type=attack_type, severity=severity,
        source_ip=source_ip, destination_ip=destination_ip, min_confidence=min_confidence,
    )
    result = AlertRepository(db).list(filters=filters, page=page, page_size=page_size, sort_by=sort_by, sort_desc=sort_desc)

    return PaginatedAlertsResponse(
        items=[AlertResponse.model_validate(row) for row in result.items],
        total=result.total, page=result.page, page_size=result.page_size,
    )


@router.get("/alerts/latest", response_model=list[AlertResponse], summary="Most recent alerts")
async def latest_alerts(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("alerts:read")),
    limit: int = Query(20, ge=1, le=200),
) -> list[AlertResponse]:
    rows = AlertRepository(db).get_latest(limit=limit)
    return [AlertResponse.model_validate(row) for row in rows]


@router.get("/alerts/{alert_id}", response_model=AlertResponse, summary="Get one alert by ID")
async def get_alert(alert_id: str, db: Session = Depends(get_db), user: User = Depends(require_permission("alerts:read"))) -> AlertResponse:
    row = AlertRepository(db).get(alert_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Alert '{alert_id}' not found")
    return AlertResponse.model_validate(row)
