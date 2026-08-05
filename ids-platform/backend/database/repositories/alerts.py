"""
Alert data access.

Every query the API layer needs (filtering, pagination, sorting) lives
here, not in the route handlers - backend/api/routes/alerts.py stays thin
and only translates query params into calls against this repository.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy import asc, desc, select
from sqlalchemy.orm import Session

from backend.database.models import Alert
from backend.utils.logger import get_logger

logger = get_logger(__name__)

ALLOWED_SORT_FIELDS = {
    "timestamp": Alert.timestamp,
    "confidence": Alert.confidence,
    "severity": Alert.severity,
}


@dataclass
class AlertFilters:
    """All optional - an unset filter means "don't restrict on this field"."""

    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    attack_type: Optional[str] = None
    severity: Optional[str] = None
    source_ip: Optional[str] = None
    destination_ip: Optional[str] = None
    min_confidence: Optional[float] = None


@dataclass
class PageResult:
    items: list[Alert]
    total: int
    page: int
    page_size: int


class AlertRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, alert: Alert) -> Alert:
        self.db.add(alert)
        self.db.flush()  # populate defaults (id, timestamp) without requiring a commit here
        logger.info("DB insert: alert id=%s attack=%s severity=%s", alert.id, alert.attack_type, alert.severity)
        return alert

    def get(self, alert_id: str) -> Optional[Alert]:
        return self.db.get(Alert, alert_id)

    def list(
        self,
        filters: Optional[AlertFilters] = None,
        page: int = 1,
        page_size: int = 50,
        sort_by: str = "timestamp",
        sort_desc: bool = True,
    ) -> PageResult:
        filters = filters or AlertFilters()
        stmt = select(Alert)

        if filters.start_date is not None:
            stmt = stmt.where(Alert.timestamp >= filters.start_date)
        if filters.end_date is not None:
            stmt = stmt.where(Alert.timestamp <= filters.end_date)
        if filters.attack_type is not None:
            stmt = stmt.where(Alert.attack_type == filters.attack_type)
        if filters.severity is not None:
            stmt = stmt.where(Alert.severity == filters.severity)
        if filters.source_ip is not None:
            stmt = stmt.where(Alert.source_ip == filters.source_ip)
        if filters.destination_ip is not None:
            stmt = stmt.where(Alert.destination_ip == filters.destination_ip)
        if filters.min_confidence is not None:
            stmt = stmt.where(Alert.confidence >= filters.min_confidence)

        total = len(self.db.execute(stmt).all())

        sort_column = ALLOWED_SORT_FIELDS.get(sort_by, Alert.timestamp)
        stmt = stmt.order_by(desc(sort_column) if sort_desc else asc(sort_column))

        page = max(1, page)
        page_size = max(1, min(page_size, 500))  # hard ceiling so a client can't force a full-table scan response
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)

        items = list(self.db.execute(stmt).scalars().all())
        return PageResult(items=items, total=total, page=page, page_size=page_size)

    def get_latest(self, limit: int = 20) -> list[Alert]:
        stmt = select(Alert).order_by(desc(Alert.timestamp)).limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    def count_since(self, since: datetime) -> int:
        stmt = select(Alert).where(Alert.timestamp >= since)
        return len(self.db.execute(stmt).all())
