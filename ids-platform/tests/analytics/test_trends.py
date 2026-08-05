"""Tests for trends.py."""

from datetime import datetime, timedelta, timezone

import pytest

from backend.analytics import trends
from backend.database.models import ResponseHistory
from tests.analytics.conftest import seed_alert


def test_attack_timeline_buckets_by_day(db_session):
    now = datetime.now(timezone.utc)
    seed_alert(db_session, "a1", timestamp=now)
    seed_alert(db_session, "a2", timestamp=now)
    seed_alert(db_session, "a3", timestamp=now - timedelta(days=1))

    timeline = trends.attack_timeline(db_session, days=30)
    counts = {point["date"]: point["count"] for point in timeline}
    today_key = now.strftime("%Y-%m-%d")
    assert counts[today_key] == 2


def test_attack_timeline_excludes_alerts_outside_the_window(db_session):
    seed_alert(db_session, "a1", timestamp=datetime.now(timezone.utc) - timedelta(days=60))
    timeline = trends.attack_timeline(db_session, days=30)
    assert timeline == []


def test_top_destination_ips(db_session):
    seed_alert(db_session, "a1", dest_ip="10.0.0.5")
    seed_alert(db_session, "a2", dest_ip="10.0.0.5")
    seed_alert(db_session, "a3", dest_ip="10.0.0.9")

    top = trends.top_destination_ips(db_session)
    assert top[0] == {"destination_ip": "10.0.0.5", "count": 2}


def test_attack_heatmap_buckets_by_day_of_week_and_hour(db_session):
    fixed_time = datetime(2026, 7, 27, 14, 30, tzinfo=timezone.utc)  # a Monday
    seed_alert(db_session, "a1", timestamp=fixed_time)

    heatmap = trends.attack_heatmap(db_session, days=30)
    assert {"day_of_week": 0, "hour": 14, "count": 1} in heatmap


def test_average_response_time_computes_delta_between_alert_and_first_response(db_session):
    alert_time = datetime.now(timezone.utc) - timedelta(minutes=10)
    seed_alert(db_session, "a1", timestamp=alert_time)
    db_session.add(ResponseHistory(
        id="r1", response_group_id="g1", alert_id="a1", action="block_ip", status="success",
        execution_time_ms=5.0, operator="automated", mode="simulation", rollback_available=True,
        timestamp=alert_time + timedelta(seconds=30),
    ))
    db_session.commit()

    avg = trends.average_response_time_seconds(db_session)
    assert avg == pytest.approx(30.0, rel=0.05)


def test_average_response_time_is_none_when_no_responses_exist(db_session):
    seed_alert(db_session, "a1")
    assert trends.average_response_time_seconds(db_session) is None
