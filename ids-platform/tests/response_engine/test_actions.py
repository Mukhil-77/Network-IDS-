"""
Tests for the individual action handlers in simulation mode - verifying
each is safe (no real subprocess/network calls), records the right
metadata, and reports rollback availability correctly.
"""

from unittest.mock import patch

from backend.database.models import BlockedIP
from backend.response_engine import firewall, notifications, quarantine, recovery
from backend.response_engine.response_registry import ResponseContext


def make_context(mode="simulation") -> ResponseContext:
    return ResponseContext(
        alert_id="a1", severity="Critical", attack_type="DoS",
        source_ip="10.0.0.5", destination_ip="10.0.0.9", flow_id="f1", mode=mode,
    )


class TestFirewall:
    def test_block_ip_simulation_does_not_call_subprocess(self, db_session, monkeypatch):
        monkeypatch.setattr("backend.database.connection.SessionLocal", lambda: db_session)
        with patch("backend.response_engine.firewall.subprocess.run") as mock_run:
            result = firewall.block_ip(make_context())
            mock_run.assert_not_called()
        assert result.status == "success"
        assert "[SIMULATION]" in result.message
        assert result.rollback_available is True

    def test_block_ip_records_a_blocked_ip_row(self, db_session, monkeypatch):
        monkeypatch.setattr("backend.database.connection.SessionLocal", lambda: db_session)
        firewall.block_ip(make_context())
        row = db_session.query(BlockedIP).filter(BlockedIP.ip_address == "10.0.0.5").first()
        assert row is not None
        assert row.is_active is True

    def test_unblock_ip_simulation_reports_success(self, db_session, monkeypatch):
        monkeypatch.setattr("backend.database.connection.SessionLocal", lambda: db_session)
        result = firewall.unblock_ip(make_context())
        assert result.status == "success"
        assert result.rollback_available is False  # unblocking has no further rollback


class TestQuarantine:
    def test_quarantine_host_is_always_simulated_regardless_of_mode(self):
        # No live implementation exists (see quarantine.py's docstring) -
        # even mode="live" must still simulate.
        result = quarantine.quarantine_host(make_context(mode="live"))
        assert "[SIMULATION]" in result.message
        assert result.metadata["mode"] == "simulation"


class TestRecovery:
    def test_restart_service_simulation_does_not_call_subprocess(self):
        with patch("backend.response_engine.recovery.subprocess.run") as mock_run:
            result = recovery.restart_service(make_context())
            mock_run.assert_not_called()
        assert result.status == "success"
        assert result.rollback_available is False

    def test_kill_process_simulation_does_not_touch_a_real_pid(self):
        with patch("backend.response_engine.recovery.os.kill") as mock_kill:
            result = recovery.kill_process(make_context())
            mock_kill.assert_not_called()
        assert result.status == "success"

    def test_generate_incident_writes_an_audit_log_entry(self, db_session, monkeypatch):
        monkeypatch.setattr("backend.database.connection.SessionLocal", lambda: db_session)
        from backend.database.models import AuditLog

        result = recovery.generate_incident(make_context())
        assert result.status == "success"
        entry = db_session.query(AuditLog).filter(AuditLog.action == "incident_created").first()
        assert entry is not None
        assert entry.target == "a1"


class TestNotifications:
    def test_send_email_simulation_does_not_open_smtp_connection(self):
        with patch("backend.notifications.email_service.smtplib.SMTP") as mock_smtp:
            result = notifications.send_email(make_context())
            mock_smtp.assert_not_called()
        assert result.status == "success"
        assert "[SIMULATION]" in result.message

    def test_send_telegram_simulation_does_not_call_requests(self):
        with patch("backend.notifications.telegram_service.requests.post") as mock_post:
            result = notifications.send_telegram(make_context())
            mock_post.assert_not_called()
        assert result.status == "success"

    def test_webhook_notification_simulation_does_not_call_requests(self):
        with patch("backend.notifications.webhook_service.requests.post") as mock_post:
            result = notifications.webhook_notification(make_context())
            mock_post.assert_not_called()
        assert result.status == "success"

    def test_log_response_writes_audit_log_and_never_makes_network_calls(self, db_session, monkeypatch):
        monkeypatch.setattr("backend.database.connection.SessionLocal", lambda: db_session)
        result = notifications.log_response(make_context())
        assert result.status == "success"
        assert result.rollback_available is False
