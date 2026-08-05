"""Tests for analytics_service.py's composition."""

from backend.analytics.analytics_service import get_overview, get_trends
from tests.analytics.conftest import seed_alert


def test_get_overview_includes_every_required_field(db_session):
    seed_alert(db_session, "a1", attack_type="DoS", severity="High", source_ip="10.0.0.1")
    seed_alert(db_session, "a2", attack_type="PortScan", severity="Low", source_ip="10.0.0.2")

    overview = get_overview(db_session)

    for key in [
        "top_attack_types", "attack_timeline", "top_source_ips", "top_destination_ips",
        "attack_heatmap", "severity_distribution", "detection_accuracy", "false_positive_rate",
        "average_detection_time_ms", "average_response_time_seconds",
    ]:
        assert key in overview

    assert overview["top_attack_types"] == {"DoS": 1, "PortScan": 1}
    assert overview["severity_distribution"] == {"High": 1, "Low": 1}


def test_false_positive_rate_is_an_honest_placeholder(db_session):
    overview = get_overview(db_session)
    assert overview["false_positive_rate"] is None


def test_get_trends_includes_timeline_and_forecast(db_session):
    seed_alert(db_session, "a1")
    result = get_trends(db_session, forecast_days=3)
    assert "attack_timeline" in result
    assert "forecast" in result
    assert len(result["forecast"]) == 3
