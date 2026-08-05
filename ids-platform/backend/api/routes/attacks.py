"""GET /attacks/top - the AttackStatistics rollup, sorted by frequency."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from backend.auth.dependencies import require_permission
from backend.auth.models import User
from sqlalchemy.orm import Session

from backend.api.schemas import TopAttackResponse
from backend.database.connection import get_db
from backend.services.history_service import HistoryService

router = APIRouter()


@router.get("/attacks/top", response_model=list[TopAttackResponse], summary="Most frequent attack types")
async def top_attacks(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("statistics:read")),
    limit: int = Query(10, ge=1, le=100),
) -> list[TopAttackResponse]:
    rows = HistoryService.get_top_attacks(db, limit=limit)
    return [TopAttackResponse.model_validate(row) for row in rows]
