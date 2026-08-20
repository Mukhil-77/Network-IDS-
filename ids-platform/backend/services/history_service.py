"""Thin composition layer backing GET /flows and GET /attacks/top - keeps those routes free of repository/query details."""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.database.repositories.alerts import PageResult
from backend.database.repositories.flows import FlowFilters, FlowRepository
from backend.database.repositories.statistics import AttackStatisticsRepository
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class HistoryService:
    @staticmethod
    def get_flows(
        db: Session,
        filters: FlowFilters | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> PageResult:
        return FlowRepository(db).list(filters=filters, page=page, page_size=page_size)

    @staticmethod
    def get_flow_summary(db: Session) -> dict:
        return FlowRepository(db).summary()

    @staticmethod
    def get_top_attacks(db: Session, limit: int = 10) -> list:
        return AttackStatisticsRepository(db).top(limit=limit)
