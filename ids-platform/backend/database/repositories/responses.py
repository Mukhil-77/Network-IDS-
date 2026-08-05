"""
Response history data access - backs GET /responses, GET /responses/{id},
GET /responses/history, and is written to by
backend/response_engine/response_history.py after every executed action.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from backend.database.models import ResponseHistory
from backend.database.repositories.alerts import PageResult
from backend.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ResponseFilters:
    alert_id: Optional[str] = None
    status: Optional[str] = None
    mode: Optional[str] = None
    action: Optional[str] = None


class ResponseRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, row: ResponseHistory) -> ResponseHistory:
        self.db.add(row)
        self.db.flush()
        logger.info(
            "DB insert: response_history id=%s action=%s status=%s mode=%s",
            row.id, row.action, row.status, row.mode,
        )
        return row

    def get(self, response_id: str) -> Optional[ResponseHistory]:
        return self.db.get(ResponseHistory, response_id)

    def list(
        self,
        filters: Optional[ResponseFilters] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> PageResult:
        filters = filters or ResponseFilters()
        stmt = select(ResponseHistory)

        if filters.alert_id is not None:
            stmt = stmt.where(ResponseHistory.alert_id == filters.alert_id)
        if filters.status is not None:
            stmt = stmt.where(ResponseHistory.status == filters.status)
        if filters.mode is not None:
            stmt = stmt.where(ResponseHistory.mode == filters.mode)
        if filters.action is not None:
            stmt = stmt.where(ResponseHistory.action == filters.action)

        total = len(self.db.execute(stmt).all())

        page = max(1, page)
        page_size = max(1, min(page_size, 500))
        stmt = stmt.order_by(desc(ResponseHistory.timestamp)).offset((page - 1) * page_size).limit(page_size)

        items = list(self.db.execute(stmt).scalars().all())
        return PageResult(items=items, total=total, page=page, page_size=page_size)

    def latest(self, limit: int = 20) -> list[ResponseHistory]:
        stmt = select(ResponseHistory).order_by(desc(ResponseHistory.timestamp)).limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    def get_by_group(self, response_group_id: str) -> list[ResponseHistory]:
        stmt = select(ResponseHistory).where(ResponseHistory.response_group_id == response_group_id)
        return list(self.db.execute(stmt).scalars().all())
