"""Tests for StatisticsService.get_summary()."""

from datetime import datetime, timezone

from backend.database.models import Alert, FlowHistory, ModelMetadataRecord
from backend.database.repositories.alerts import AlertRepository
from backend.database.repositories.flows import FlowRepository
from backend.services.statistics_service import StatisticsService


def seed_alert(db, flow_id, attack_type="DoS", severity="High", confidence=90.0, latency_ms=5.0):
    FlowRepository(db).create(FlowHistory(
        id=flow_id, protocol="TCP", source_ip="10.0.0.1", destination_ip="10.0.0.2",
        source_port=5000, destination_port=80,
        start_time=datetime.now(timezone.utc), end_time=datetime.now(timezone.utc),
        packet_count=1, byte_count=100,
    ))
    AlertRepository(db).create(Alert(
        attack_type=attack_type, confidence=confidence, severity=severity,
        source_ip="10.0.0.1", destination_ip="10.0.0.2", protocol="TCP", flow_id=flow_id,
        packet_count=1, bytes=100, model_version="v1", processing_time_ms=latency_ms,
    ))


def test_get_summary_with_no_alerts(db_session):
    summary = StatisticsService().get_summary(db_session)

    assert summary["threat_count"] == 0
    assert summary["threats_by_type"] == {}
    assert summary["average_prediction_latency_ms"] == 0.0
    assert summary["detection_accuracy"] is None  # no ModelMetadataRecord synced


def test_get_summary_reflects_seeded_alerts(db_session):
    seed_alert(db_session, "f1", attack_type="DoS", latency_ms=4.0)
    seed_alert(db_session, "f2", attack_type="DoS", latency_ms=6.0)
    db_session.commit()

    summary = StatisticsService().get_summary(db_session)

    assert summary["threat_count"] == 2
    assert summary["threats_by_type"] == {"DoS": 2}
    assert summary["average_prediction_latency_ms"] == 5.0


def test_get_summary_reports_detection_accuracy_from_latest_model(db_session):
    db_session.add(ModelMetadataRecord(
        version="v1", model_name="rf", training_date="2026-01-01", accuracy=0.91,
        precision=0.9, recall=0.89, f1_score=0.895, num_features=8, pca_components=4,
        sklearn_version="1.3.0", project_version="0.1.0",
    ))
    db_session.commit()

    summary = StatisticsService().get_summary(db_session)
    assert summary["detection_accuracy"] == 0.91
