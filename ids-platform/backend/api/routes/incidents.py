"""GET /incidents, POST /incidents, PUT /incidents/{id}."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.api.schemas import IncidentCreateRequest, IncidentResponse, IncidentUpdateRequest, PaginatedIncidents
from backend.auth.dependencies import require_permission
from backend.auth.models import User
from backend.database.connection import get_db
from backend.database.repositories.incidents import IncidentFilters, IncidentRepository
from backend.services import incident_service

router = APIRouter()


@router.get("/incidents", response_model=PaginatedIncidents, summary="List incidents with filtering and pagination")
async def list_incidents(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("incidents:read")),
    status_filter: str | None = Query(None, alias="status"),
    severity: str | None = Query(None),
    owner: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
) -> PaginatedIncidents:
    filters = IncidentFilters(status=status_filter, severity=severity, owner=owner)
    result = IncidentRepository(db).list(filters=filters, page=page, page_size=page_size)
    return PaginatedIncidents(
        items=[IncidentResponse.model_validate(i) for i in result.items],
        total=result.total, page=result.page, page_size=result.page_size,
    )


@router.post("/incidents", response_model=IncidentResponse, status_code=status.HTTP_201_CREATED, summary="Open a new incident")
async def create_incident(
    payload: IncidentCreateRequest, db: Session = Depends(get_db),
    user: User = Depends(require_permission("incidents:write")),
) -> IncidentResponse:
    incident = incident_service.create_incident(
        db, title=payload.title, description=payload.description, severity=payload.severity,
        priority=payload.priority, created_by=user.username, alert_id=payload.alert_id,
    )
    return IncidentResponse.model_validate(incident)


@router.put("/incidents/{incident_id}", response_model=IncidentResponse, summary="Update an incident's status, owner, priority, or add a note")
async def update_incident(
    incident_id: str, payload: IncidentUpdateRequest, db: Session = Depends(get_db),
    user: User = Depends(require_permission("incidents:write")),
) -> IncidentResponse:
    try:
        incident = incident_service.update_incident(
            db, incident_id, user.username,
            status=payload.status, owner=payload.owner, priority=payload.priority, note=payload.note,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except incident_service.InvalidTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return IncidentResponse.model_validate(incident)
