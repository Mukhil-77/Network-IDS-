"""GET /flows - paginated, filterable flow history."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query

from backend.auth.dependencies import require_permission
from backend.auth.models import User
from sqlalchemy.orm import Session

from backend.api.schemas import FlowHistoryResponse, PaginatedFlowsResponse
from backend.database.connection import get_db
from backend.database.repositories.flows import FlowFilters
from backend.services.history_service import HistoryService

router = APIRouter()


@router.get("/flows", response_model=PaginatedFlowsResponse, summary="List reconstructed network flows")
async def list_flows(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("flows:read")),
    source_ip: Optional[str] = Query(None),
    destination_ip: Optional[str] = Query(None),
    protocol: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
) -> PaginatedFlowsResponse:
    filters = FlowFilters(source_ip=source_ip, destination_ip=destination_ip, protocol=protocol)
    result = HistoryService.get_flows(db, filters=filters, page=page, page_size=page_size)

    return PaginatedFlowsResponse(
        items=[FlowHistoryResponse.model_validate(row) for row in result.items],
        total=result.total, page=result.page, page_size=result.page_size,
    )


@router.get("/flows/summary", summary="Aggregate totals and top talkers across flow history")
async def flow_summary(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("flows:read")),
) -> dict:
    return HistoryService.get_flow_summary(db)
