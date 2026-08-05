"""Tests for enrichment.py."""

from datetime import datetime, timezone

from backend.database.models import Alert, FlowHistory
from backend.threat_intelligence.enrichment import enrich_and_tag
from backend.threat_intelligence.indicators import ThreatTag
from backend.threat_intelligence.reputation import ReputationRegistry, StaticIndicatorProvider


def seed_alert(db, alert_id="a1", source_ip="1.2.3.4"):
    db.add(FlowHistory(
        id="f1", protocol="TCP", source_ip=source_ip, destination_ip="10.0.0.1",
        source_port=1, destination_port=2,
        start_time=datetime.now(timezone.utc), end_time=datetime.now(timezone.utc),
        packet_count=1, byte_count=1,
    ))
    db.add(Alert(
        id=alert_id, attack_type="DoS", confidence=90.0, severity="High",
        source_ip=source_ip, destination_ip="10.0.0.1", protocol="TCP", flow_id="f1",
        packet_count=1, bytes=1, status="new", model_version="v1", processing_time_ms=1.0,
    ))
    db.commit()


def use_test_registry(monkeypatch, db_session):
    from contextlib import contextmanager

    @contextmanager
    def fake_session_scope():
        yield db_session
        db_session.commit()

    monkeypatch.setattr("backend.threat_intelligence.enrichment.session_scope", fake_session_scope)


def test_enrich_and_tag_writes_the_tag_onto_the_alert_row(db_session, monkeypatch):
    use_test_registry(monkeypatch, db_session)
    seed_alert(db_session)
    from backend.database.models import ThreatIndicator
    db_session.add(ThreatIndicator(value="1.2.3.4", indicator_type="ip", tag="Known Malicious", source="internal", confidence=95.0))
    db_session.commit()

    registry = ReputationRegistry()
    registry.register_provider(StaticIndicatorProvider())

    tag = enrich_and_tag({"id": "a1", "source_ip": "1.2.3.4"}, registry=registry)

    assert tag == ThreatTag.KNOWN_MALICIOUS
    refreshed = db_session.get(Alert, "a1")
    assert refreshed.threat_tag == "Known Malicious"


def test_enrich_and_tag_defaults_to_unknown_for_an_unrecognized_ip(db_session, monkeypatch):
    use_test_registry(monkeypatch, db_session)
    seed_alert(db_session, source_ip="9.9.9.9")

    registry = ReputationRegistry()
    registry.register_provider(StaticIndicatorProvider())

    tag = enrich_and_tag({"id": "a1", "source_ip": "9.9.9.9"}, registry=registry)
    assert tag == ThreatTag.UNKNOWN


def test_enrich_and_tag_does_not_raise_if_the_alert_no_longer_exists(db_session, monkeypatch):
    use_test_registry(monkeypatch, db_session)
    registry = ReputationRegistry()
    registry.register_provider(StaticIndicatorProvider())

    tag = enrich_and_tag({"id": "does-not-exist", "source_ip": "1.2.3.4"}, registry=registry)
    assert tag == ThreatTag.UNKNOWN
