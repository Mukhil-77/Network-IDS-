"""Tests for ResponseService: the full workflow, alert status updates, and rollback."""

from datetime import datetime, timezone

import pytest

from backend.database.models import Alert, FlowHistory
from backend.response_engine.response_rules import PolicyEngine
from backend.response_engine.response_service import ResponseService
from backend.websocket.broadcaster import AlertBroadcaster
from backend.websocket.manager import ConnectionManager


def seed_alert(db, alert_id="a1", severity="Critical"):
    db.add(FlowHistory(
        id="f1", protocol="TCP", source_ip="10.0.0.5", destination_ip="10.0.0.9",
        source_port=1, destination_port=2,
        start_time=datetime.now(timezone.utc), end_time=datetime.now(timezone.utc),
        packet_count=1, byte_count=1,
    ))
    db.add(Alert(
        id=alert_id, attack_type="DoS", confidence=90.0, severity=severity,
        source_ip="10.0.0.5", destination_ip="10.0.0.9", protocol="TCP", flow_id="f1",
        packet_count=1, bytes=1, status="new", model_version="v1", processing_time_ms=1.0,
    ))
    db.commit()


@pytest.fixture
def service(db_session, monkeypatch, policy_engine):
    monkeypatch.setattr("backend.database.connection.SessionLocal", lambda: db_session)
    seed_alert(db_session)
    return ResponseService(policy_engine=policy_engine, broadcaster=AlertBroadcaster(ConnectionManager()))


def alert_summary(alert_id="a1", severity="Critical"):
    return {"id": alert_id, "severity": severity, "attack_type": "DoS", "source_ip": "10.0.0.5", "destination_ip": "10.0.0.9", "flow_id": "f1"}


class TestHandleAlert:
    def test_critical_severity_runs_all_five_configured_actions(self, service):
        rows = service.handle_alert(alert_summary(severity="Critical"))
        assert {r.action for r in rows} == {"block_ip", "quarantine_host", "send_email", "send_telegram", "log_response"}

    def test_low_severity_runs_only_log_response(self, service):
        rows = service.handle_alert(alert_summary(severity="Low"))
        assert [r.action for r in rows] == ["log_response"]

    def test_unmapped_severity_runs_nothing(self, service):
        rows = service.handle_alert(alert_summary(severity="Unmapped"))
        assert rows == []

    def test_all_success_marks_alert_responded(self, service, db_session):
        service.handle_alert(alert_summary(severity="Low"))
        alert = db_session.get(Alert, "a1")
        assert alert.status == "responded"

    def test_every_row_recorded_in_simulation_mode(self, service):
        rows = service.handle_alert(alert_summary(severity="Critical"))
        assert all(r.mode == "simulation" for r in rows)
        assert all(r.operator == "automated" for r in rows)


class TestExecuteManual:
    def test_explicit_action_list_overrides_policy(self, service):
        rows = service.execute_manual(alert_summary(), actions=["log_response"], operator="jane")
        assert [r.action for r in rows] == ["log_response"]
        assert rows[0].operator == "jane"

    def test_no_action_list_falls_back_to_policy(self, service):
        rows = service.execute_manual(alert_summary(severity="Medium"))
        assert {r.action for r in rows} == {"notify_analyst", "increase_monitoring"}

    def test_explicit_mode_overrides_policy_simulation_flag(self, service, monkeypatch):
        # Even with mode="live" requested, simulation.py's ENABLE_LIVE_RESPONSE_ACTIONS
        # gate defaults false, so the action itself still simulates - but
        # the ResponseHistory row records the *requested* mode.
        rows = service.execute_manual(alert_summary(), actions=["log_response"], mode="live")
        assert rows[0].mode == "live"


class TestRollback:
    def test_rollback_block_ip_executes_unblock_ip(self, service):
        rows = service.handle_alert(alert_summary(severity="Critical"))
        block_row = next(r for r in rows if r.action == "block_ip")

        rollback_row = service.rollback(block_row.id)
        assert rollback_row.action == "unblock_ip"
        assert rollback_row.status == "success"

    def test_rollback_marks_original_as_rolled_back(self, service, db_session):
        rows = service.handle_alert(alert_summary(severity="Critical"))
        block_row = next(r for r in rows if r.action == "block_ip")

        service.rollback(block_row.id)

        from backend.database.models import ResponseHistory
        refreshed = db_session.get(ResponseHistory, block_row.id)
        assert refreshed.rolled_back is True

    def test_rollback_twice_raises(self, service):
        rows = service.handle_alert(alert_summary(severity="Critical"))
        block_row = next(r for r in rows if r.action == "block_ip")

        service.rollback(block_row.id)
        with pytest.raises(ValueError, match="already rolled back"):
            service.rollback(block_row.id)

    def test_rollback_of_action_without_rollback_raises(self, service):
        rows = service.handle_alert(alert_summary(severity="Critical"))
        email_row = next(r for r in rows if r.action == "send_email")

        with pytest.raises(ValueError, match="no rollback action"):
            service.rollback(email_row.id)

    def test_rollback_of_unknown_response_id_raises(self, service):
        with pytest.raises(ValueError, match="not found"):
            service.rollback("does-not-exist")
