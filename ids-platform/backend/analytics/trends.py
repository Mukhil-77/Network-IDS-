"""
Time-bucketed and dimensional breakdowns over Alerts/ResponseHistory -
extends what backend/database/repositories/statistics.py (Milestone 6)
already does (threats_by_type, threats_by_severity, top_source_ips) with
the dimensions Milestone 10 additionally needs: a day-level timeline,
top *destination* IPs, and hour-of-day/day-of-week heatmap data. Reuses
the same Alert/ResponseHistory tables - no new tables for any of this.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.database.models import Alert, ResponseHistory


def attack_timeline(db: Session, days: int = 30) -> list[dict]:
    """Alert count per day, over the last `days` days."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    timestamps = db.execute(select(Alert.timestamp).where(Alert.timestamp >= since)).scalars().all()

    buckets: dict[str, int] = {}
    for ts in timestamps:
        key = ts.strftime("%Y-%m-%d")
        buckets[key] = buckets.get(key, 0) + 1

    return [{"date": date, "count": count} for date, count in sorted(buckets.items())]


def top_destination_ips(db: Session, limit: int = 10) -> list[dict]:
    stmt = (
        select(Alert.destination_ip, func.count().label("count"))
        .group_by(Alert.destination_ip)
        .order_by(func.count().desc())
        .limit(limit)
    )
    return [{"destination_ip": ip, "count": count} for ip, count in db.execute(stmt).all()]


def attack_heatmap(db: Session, days: int = 30) -> list[dict]:
    """
    Alert count by (day-of-week, hour-of-day), over the last `days` days -
    the classic SOC "when do attacks happen" heatmap. day_of_week: 0=Monday.
    """
    since = datetime.now(timezone.utc) - timedelta(days=days)
    timestamps = db.execute(select(Alert.timestamp).where(Alert.timestamp >= since)).scalars().all()

    buckets: dict[tuple[int, int], int] = {}
    for ts in timestamps:
        key = (ts.weekday(), ts.hour)
        buckets[key] = buckets.get(key, 0) + 1

    return [{"day_of_week": dow, "hour": hour, "count": count} for (dow, hour), count in sorted(buckets.items())]


def average_response_time_seconds(db: Session) -> float | None:
    """
    Mean time between an alert's creation and its first response action -
    "Average Response Time" from the spec. Reuses Alert (Milestone 6) and
    ResponseHistory (Milestone 8) directly; no new table.
    """
    stmt = (
        select(Alert.timestamp, func.min(ResponseHistory.timestamp))
        .join(ResponseHistory, ResponseHistory.alert_id == Alert.id)
        .group_by(Alert.id, Alert.timestamp)
    )
    deltas = [
        (response_ts - alert_ts).total_seconds()
        for alert_ts, response_ts in db.execute(stmt).all()
        if response_ts is not None
    ]
    if not deltas:
        return None
    return sum(deltas) / len(deltas)
