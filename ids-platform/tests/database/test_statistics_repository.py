"""Tests for backend/database/repositories/statistics.py."""

from datetime import datetime, timezone

from backend.database.models import Alert, AttackStatistics, FlowHistory
from backend.database.repositories import statistics as stats_repo
from backend.database.repositories.alerts import AlertRepository
from backend.database.repositories.flows import FlowRepository


def seed_alert(db, flow_id, attack_type, severity, source_ip="10.0.0.1", confidence=90.0, latency_ms=5.0):
    FlowRepository(db).create(FlowHistory(
        id=flow_id, protocol="TCP", source_ip=source_ip, destination_ip="10.0.0.2",
        source_port=5000, destination_port=80,
        start_time=datetime.now(timezone.utc), end_time=datetime.now(timezone.utc),
        packet_count=1, byte_count=100,
    ))
    return AlertRepository(db).create(Alert(
        attack_type=attack_type, confidence=confidence, severity=severity,
        source_ip=source_ip, destination_ip="10.0.0.2", protocol="TCP", flow_id=flow_id,
        packet_count=1, bytes=100, model_version="v1", processing_time_ms=latency_ms,
    ))


class TestAttackStatisticsRepository:
    def test_upsert_creates_new_row(self, db_session):
        repo = stats_repo.AttackStatisticsRepository(db_session)
        row = repo.upsert("DoS", confidence=90.0, seen_at=datetime.now(timezone.utc))
        db_session.commit()

        assert row.total_count == 1
        assert row.avg_confidence == 90.0

    def test_upsert_increments_and_averages(self, db_session):
        repo = stats_repo.AttackStatisticsRepository(db_session)
        repo.upsert("DoS", confidence=80.0, seen_at=datetime.now(timezone.utc))
        repo.upsert("DoS", confidence=100.0, seen_at=datetime.now(timezone.utc))
        db_session.commit()

        row = db_session.get(AttackStatistics, "DoS")
        assert row.total_count == 2
        assert row.avg_confidence == 90.0  # (80 + 100) / 2

    def test_top_sorts_by_count_descending(self, db_session):
        repo = stats_repo.AttackStatisticsRepository(db_session)
        repo.upsert("DoS", confidence=90.0, seen_at=datetime.now(timezone.utc))
        repo.upsert("PortScan", confidence=90.0, seen_at=datetime.now(timezone.utc))
        repo.upsert("PortScan", confidence=90.0, seen_at=datetime.now(timezone.utc))
        db_session.commit()

        top = repo.top(limit=10)
        assert top[0].attack_type == "PortScan"
        assert top[0].total_count == 2


class TestAggregateQueries:
    def test_threat_count(self, db_session):
        seed_alert(db_session, "f1", "DoS", "High")
        seed_alert(db_session, "f2", "PortScan", "Medium")
        db_session.commit()

        assert stats_repo.threat_count(db_session) == 2

    def test_threats_by_type(self, db_session):
        seed_alert(db_session, "f1", "DoS", "High")
        seed_alert(db_session, "f2", "DoS", "High")
        seed_alert(db_session, "f3", "PortScan", "Low")
        db_session.commit()

        breakdown = stats_repo.threats_by_type(db_session)
        assert breakdown == {"DoS": 2, "PortScan": 1}

    def test_threats_by_severity(self, db_session):
        seed_alert(db_session, "f1", "DoS", "High")
        seed_alert(db_session, "f2", "PortScan", "Low")
        db_session.commit()

        breakdown = stats_repo.threats_by_severity(db_session)
        assert breakdown == {"High": 1, "Low": 1}

    def test_top_source_ips(self, db_session):
        seed_alert(db_session, "f1", "DoS", "High", source_ip="1.1.1.1")
        seed_alert(db_session, "f2", "DoS", "High", source_ip="1.1.1.1")
        seed_alert(db_session, "f3", "DoS", "High", source_ip="2.2.2.2")
        db_session.commit()

        top = stats_repo.top_source_ips(db_session)
        assert top[0] == {"source_ip": "1.1.1.1", "count": 2}

    def test_average_prediction_latency(self, db_session):
        seed_alert(db_session, "f1", "DoS", "High", latency_ms=4.0)
        seed_alert(db_session, "f2", "DoS", "High", latency_ms=6.0)
        db_session.commit()

        assert stats_repo.average_prediction_latency_ms(db_session) == 5.0

    def test_average_prediction_latency_with_no_alerts_is_zero(self, db_session):
        assert stats_repo.average_prediction_latency_ms(db_session) == 0.0
