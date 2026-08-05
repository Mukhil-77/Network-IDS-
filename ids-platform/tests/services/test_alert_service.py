"""Tests for AlertService.handle_detection()."""

from sqlalchemy import select

from backend.database.models import Alert as AlertRow
from backend.database.models import AttackStatistics, FlowHistory
from backend.detection.alert import Alert as DetectionAlert
from backend.ml.schemas import PredictionResponse
from backend.packet_capture.flow_manager import Flow
from backend.services.alert_service import AlertService
from backend.websocket.broadcaster import AlertBroadcaster
from backend.websocket.manager import ConnectionManager


def make_inputs(attack="DoS", severity="High", confidence=95.0, flow_id="flow-1"):
    flow = Flow(
        flow_id=flow_id, key=("10.0.0.1", 5000, "10.0.0.9", 80, "TCP"),
        protocol="TCP", src_ip="10.0.0.1", dst_ip="10.0.0.9", src_port=5000, dst_port=80,
        start_time=1000.0, last_seen=1001.0,
    )
    flow.fwd_lengths = [100, 100]
    flow.bwd_lengths = [200]

    prediction = PredictionResponse(prediction=attack, confidence=confidence, severity=severity, model_version="v1", latency_ms=6.5)
    alert = DetectionAlert(
        attack=attack, severity=severity, confidence=confidence,
        source_ip="10.0.0.1", destination_ip="10.0.0.9", protocol="TCP", flow_id=flow_id,
        source_port=5000, destination_port=80, model_version="v1",
    )
    return alert, flow, prediction


def _use_test_db(monkeypatch, db_session):
    """Point AlertService's session_scope() at the shared test session (see database/conftest.py)."""
    from contextlib import contextmanager

    @contextmanager
    def fake_session_scope():
        yield db_session
        db_session.commit()

    monkeypatch.setattr("backend.services.alert_service.session_scope", fake_session_scope)


def test_handle_detection_persists_flow_and_alert(db_session, monkeypatch):
    _use_test_db(monkeypatch, db_session)
    service = AlertService(broadcaster=AlertBroadcaster(ConnectionManager()))

    alert, flow, prediction = make_inputs()
    service.handle_detection(alert, flow, prediction)

    flow_row = db_session.get(FlowHistory, "flow-1")
    alert_row = db_session.execute(select(AlertRow).where(AlertRow.flow_id == "flow-1")).scalars().first()

    assert flow_row is not None
    assert flow_row.packet_count == 3
    assert alert_row is not None
    assert alert_row.attack_type == "DoS"
    assert alert_row.processing_time_ms == 6.5


def test_handle_detection_upserts_attack_statistics(db_session, monkeypatch):
    _use_test_db(monkeypatch, db_session)
    service = AlertService(broadcaster=AlertBroadcaster(ConnectionManager()))

    service.handle_detection(*make_inputs(attack="DoS", confidence=80.0, flow_id="f1"))
    service.handle_detection(*make_inputs(attack="DoS", confidence=100.0, flow_id="f2"))

    row = db_session.get(AttackStatistics, "DoS")
    assert row.total_count == 2
    assert row.avg_confidence == 90.0


def test_handle_detection_broadcasts_alert(db_session, monkeypatch):
    _use_test_db(monkeypatch, db_session)
    published = []

    class FakeBroadcaster:
        def publish_alert_threadsafe(self, payload):
            published.append(payload)

    service = AlertService(broadcaster=FakeBroadcaster())
    alert, flow, prediction = make_inputs()
    service.handle_detection(alert, flow, prediction)

    assert len(published) == 1
    assert published[0]["attack"] == "DoS"


def test_handle_detection_does_not_raise_on_persistence_failure(monkeypatch):
    def broken_session_scope():
        raise RuntimeError("db unavailable")

    monkeypatch.setattr("backend.services.alert_service.session_scope", broken_session_scope)

    published = []

    class FakeBroadcaster:
        def publish_alert_threadsafe(self, payload):
            published.append(payload)

    service = AlertService(broadcaster=FakeBroadcaster())
    alert, flow, prediction = make_inputs()

    service.handle_detection(alert, flow, prediction)  # must not raise

    assert published == []  # broadcast is skipped if persistence failed
