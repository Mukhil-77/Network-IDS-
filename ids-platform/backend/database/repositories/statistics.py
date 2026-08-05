"""
Two related but distinct jobs live here:

    1. AttackStatisticsRepository - maintains the `attack_statistics`
       rollup table (one row per attack type, upserted on every alert).
       This is what makes GET /attacks/top fast (indexed lookup + sort on
       a handful of rows) instead of a GROUP BY over the entire alerts
       table on every request.

    2. Aggregate query functions - read-only analytics computed directly
       from `alerts` (threats/minute, severity breakdown, top source IPs,
       average latency). These don't need their own maintained table -
       they're cheap enough to compute on demand and always exactly
       correct, with no rollup-drift risk.

statistics_service.py composes both into the single GET /statistics response.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.database.models import Alert, AttackStatistics
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class AttackStatisticsRepository:
    def __init__(self, db: Session):
        self.db = db

    def upsert(self, attack_type: str, confidence: float, seen_at: datetime) -> AttackStatistics:
        """
        Increment `attack_type`'s running count and rolling average
        confidence. Called once per alert (see alert_service.py).
        """
        row = self.db.get(AttackStatistics, attack_type)
        if row is None:
            row = AttackStatistics(attack_type=attack_type, total_count=0, avg_confidence=0.0)
            self.db.add(row)

        new_count = row.total_count + 1
        row.avg_confidence = ((row.avg_confidence * row.total_count) + confidence) / new_count
        row.total_count = new_count
        row.last_seen = seen_at

        self.db.flush()
        return row

    def top(self, limit: int = 10) -> list[AttackStatistics]:
        stmt = select(AttackStatistics).order_by(AttackStatistics.total_count.desc()).limit(limit)
        return list(self.db.execute(stmt).scalars().all())


def threat_count(db: Session, since: datetime | None = None) -> int:
    stmt = select(func.count()).select_from(Alert)
    if since is not None:
        stmt = stmt.where(Alert.timestamp >= since)
    return db.execute(stmt).scalar_one()


def threats_per_minute(db: Session, window_minutes: int = 60) -> list[dict]:
    """Alert count bucketed by minute, over the last `window_minutes` - powers a "threats over time" chart."""
    since = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
    stmt = select(Alert.timestamp).where(Alert.timestamp >= since)
    timestamps = db.execute(stmt).scalars().all()

    buckets: dict[str, int] = {}
    for ts in timestamps:
        bucket_key = ts.strftime("%Y-%m-%dT%H:%M")
        buckets[bucket_key] = buckets.get(bucket_key, 0) + 1

    return [{"minute": minute, "count": count} for minute, count in sorted(buckets.items())]


def threats_by_type(db: Session) -> dict[str, int]:
    stmt = select(Alert.attack_type, func.count()).group_by(Alert.attack_type)
    return {attack_type: count for attack_type, count in db.execute(stmt).all()}


def threats_by_severity(db: Session) -> dict[str, int]:
    stmt = select(Alert.severity, func.count()).group_by(Alert.severity)
    return {severity: count for severity, count in db.execute(stmt).all()}


def top_source_ips(db: Session, limit: int = 10) -> list[dict]:
    stmt = (
        select(Alert.source_ip, func.count().label("count"))
        .group_by(Alert.source_ip)
        .order_by(func.count().desc())
        .limit(limit)
    )
    return [{"source_ip": ip, "count": count} for ip, count in db.execute(stmt).all()]


def average_prediction_latency_ms(db: Session) -> float:
    stmt = select(func.avg(Alert.processing_time_ms))
    result = db.execute(stmt).scalar_one_or_none()
    return float(result) if result is not None else 0.0
