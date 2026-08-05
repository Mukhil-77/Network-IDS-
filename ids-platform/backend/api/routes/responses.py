"""
POST /responses/execute, POST /responses/rollback, GET /responses,
GET /responses/{id}, GET /responses/history, GET /response-rules, PUT /response-rules.

Every route is a thin wrapper: response_service.py and response_rules.py
own all the actual logic; this module only does request/response
translation and HTTP status codes.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.api.schemas import (
    PaginatedResponses,
    ResponseExecuteRequest,
    ResponseHistoryEntry,
    ResponseRollbackRequest,
    ResponseRulesResponse,
    ResponseRulesUpdateRequest,
)
from backend.auth.dependencies import require_permission
from backend.auth.models import User
from backend.database.connection import get_db
from backend.database.models import Alert as AlertRow
from backend.database.repositories.responses import ResponseFilters, ResponseRepository
from backend.response_engine.response_registry import list_actions
from backend.response_engine.response_rules import InvalidPolicyError, policy_engine
from backend.response_engine.response_service import response_service

router = APIRouter()


def _alert_to_summary(alert: AlertRow) -> dict:
    return {
        "id": alert.id, "severity": alert.severity, "attack_type": alert.attack_type,
        "source_ip": alert.source_ip, "destination_ip": alert.destination_ip, "flow_id": alert.flow_id,
    }


@router.post("/responses/execute", response_model=list[ResponseHistoryEntry], summary="Trigger a response for an alert")
async def execute_response(
    payload: ResponseExecuteRequest, db: Session = Depends(get_db),
    user: User = Depends(require_permission("responses:execute")),
) -> list[ResponseHistoryEntry]:
    alert = db.get(AlertRow, payload.alert_id)
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Alert '{payload.alert_id}' not found")

    if payload.actions is not None:
        unknown = [a for a in payload.actions if a not in list_actions()]
        if unknown:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown action(s): {unknown}")

    # The authenticated user's real username, not whatever the client sent
    # in the request body - so ResponseHistory.operator (and its audit log
    # entry) can't be spoofed to attribute an action to someone else.
    rows = response_service.execute_manual(
        _alert_to_summary(alert), actions=payload.actions, mode=payload.mode, operator=user.username,
    )
    return [ResponseHistoryEntry.model_validate(row) for row in rows]


@router.post("/responses/rollback", response_model=ResponseHistoryEntry, summary="Roll back a previously executed response action")
async def rollback_response(
    payload: ResponseRollbackRequest,
    user: User = Depends(require_permission("responses:execute")),
) -> ResponseHistoryEntry:
    try:
        row = response_service.rollback(payload.response_id, operator=user.username)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ResponseHistoryEntry.model_validate(row)


@router.get("/responses", response_model=PaginatedResponses, summary="List response history with filtering and pagination")
async def list_responses(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("responses:read")),
    alert_id: str | None = Query(None),
    action_status: str | None = Query(None, alias="status"),
    mode: str | None = Query(None),
    action: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
) -> PaginatedResponses:
    filters = ResponseFilters(alert_id=alert_id, status=action_status, mode=mode, action=action)
    result = ResponseRepository(db).list(filters=filters, page=page, page_size=page_size)
    return PaginatedResponses(
        items=[ResponseHistoryEntry.model_validate(row) for row in result.items],
        total=result.total, page=result.page, page_size=result.page_size,
    )


@router.get("/responses/history", response_model=list[ResponseHistoryEntry], summary="Most recent response actions")
async def response_history_feed(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("responses:read")),
    limit: int = Query(20, ge=1, le=200),
) -> list[ResponseHistoryEntry]:
    rows = ResponseRepository(db).latest(limit=limit)
    return [ResponseHistoryEntry.model_validate(row) for row in rows]


@router.get("/responses/{response_id}", response_model=ResponseHistoryEntry, summary="Get one response history entry")
async def get_response(
    response_id: str, db: Session = Depends(get_db),
    user: User = Depends(require_permission("responses:read")),
) -> ResponseHistoryEntry:
    row = ResponseRepository(db).get(response_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Response '{response_id}' not found")
    return ResponseHistoryEntry.model_validate(row)


@router.get("/response-rules", response_model=ResponseRulesResponse, summary="Current response policy configuration")
async def get_response_rules(user: User = Depends(require_permission("settings:read"))) -> ResponseRulesResponse:
    return ResponseRulesResponse(
        simulation_mode=policy_engine.is_simulation_mode(),
        policies=policy_engine.get_all_policies(),
        available_actions=list_actions(),
    )


@router.put("/response-rules", response_model=ResponseRulesResponse, summary="Update response policy configuration")
async def update_response_rules(
    payload: ResponseRulesUpdateRequest,
    user: User = Depends(require_permission("settings:write")),
) -> ResponseRulesResponse:
    try:
        policy_engine.update(policies=payload.policies, simulation_mode=payload.simulation_mode)
    except InvalidPolicyError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return ResponseRulesResponse(
        simulation_mode=policy_engine.is_simulation_mode(),
        policies=policy_engine.get_all_policies(),
        available_actions=list_actions(),
    )
