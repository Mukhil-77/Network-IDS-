"""GET /threat-intelligence."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.api.schemas import ThreatIndicatorResponse
from backend.auth.dependencies import require_permission
from backend.auth.models import User
from backend.database.connection import get_db
from backend.database.models import ThreatIndicator

router = APIRouter()


@router.get("/threat-intelligence", response_model=list[ThreatIndicatorResponse], summary="List known threat indicators")
async def list_indicators(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("threat_intel:read")),
    tag: str | None = Query(None, description="Filter by ThreatTag, e.g. 'Known Malicious'"),
    limit: int = Query(100, ge=1, le=1000),
) -> list[ThreatIndicatorResponse]:
    stmt = select(ThreatIndicator)
    if tag is not None:
        stmt = stmt.where(ThreatIndicator.tag == tag)
    stmt = stmt.limit(limit)

    rows = db.execute(stmt).scalars().all()
    return [ThreatIndicatorResponse.model_validate(row) for row in rows]
