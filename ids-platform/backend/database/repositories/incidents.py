"""Incident data access - backs GET/POST/PUT /incidents."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from backend.database.models import Incident
from backend.database.repositories.alerts import PageResult
from backend.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class IncidentFilters:
    status: Optional[str] = None
    severity: Optional[str] = None
    owner: Optional[str] = None


class IncidentRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, incident: Incident) -> Incident:
        self.db.add(incident)
        self.db.flush()
        logger.info("DB insert: incident id=%s title=%s severity=%s", incident.id, incident.title, incident.severity)
        return incident

    def get(self, incident_id: str) -> Optional[Incident]:
        return self.db.get(Incident, incident_id)

    def list(self, filters: Optional[IncidentFilters] = None, page: int = 1, page_size: int = 50) -> PageResult:
        filters = filters or IncidentFilters()
        stmt = select(Incident)

        if filters.status is not None:
            stmt = stmt.where(Incident.status == filters.status)
        if filters.severity is not None:
            stmt = stmt.where(Incident.severity == filters.severity)
        if filters.owner is not None:
            stmt = stmt.where(Incident.owner == filters.owner)

        total = len(self.db.execute(stmt).all())
        page = max(1, page)
        page_size = max(1, min(page_size, 500))
        stmt = stmt.order_by(desc(Incident.created_at)).offset((page - 1) * page_size).limit(page_size)

        items = list(self.db.execute(stmt).scalars().all())
        return PageResult(items=items, total=total, page=page, page_size=page_size)

    def counts_by_status(self) -> dict[str, int]:
        from sqlalchemy import func
        stmt = select(Incident.status, func.count()).group_by(Incident.status)
        return {status: count for status, count in self.db.execute(stmt).all()}
