"""
Composes backend.database.repositories.statistics's queries (plus the
latest ModelMetadataRecord) into the single dict GET /statistics returns.
No route ever queries a repository directly - this is the one place that
decision is made, so the response shape only needs to change in one spot.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from backend.database.models import ModelMetadataRecord
from backend.database.repositories import statistics as stats_repo
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class StatisticsService:
    def get_summary(self, db: Session, window_minutes: int = 60) -> dict:
        threats_per_minute = stats_repo.threats_per_minute(db, window_minutes=window_minutes)

        summary = {
            "threat_count": stats_repo.threat_count(db),
            "threats_per_minute": threats_per_minute,
            "threats_by_type": stats_repo.threats_by_type(db),
            "threats_by_severity": stats_repo.threats_by_severity(db),
            "top_source_ips": stats_repo.top_source_ips(db),
            "detection_accuracy": self._latest_model_accuracy(db),
            "average_prediction_latency_ms": stats_repo.average_prediction_latency_ms(db),
        }
        logger.info(
            "Statistics computed: threat_count=%d, distinct_attack_types=%d",
            summary["threat_count"], len(summary["threats_by_type"]),
        )
        return summary

    @staticmethod
    def _latest_model_accuracy(db: Session) -> float | None:
        """
        The trained model's own evaluated accuracy (from metadata.json, see
        artifacts.build_metadata) - NOT a live accuracy figure. Live network
        traffic has no ground-truth labels, so "detection accuracy" against
        real traffic literally cannot be computed; this is the closest
        honest proxy available, and is clearly named to avoid implying
        otherwise.
        """
        stmt = select(ModelMetadataRecord).order_by(desc(ModelMetadataRecord.recorded_at)).limit(1)
        row = db.execute(stmt).scalars().first()
        return row.accuracy if row is not None else None
