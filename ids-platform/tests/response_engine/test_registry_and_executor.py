"""Tests for response_registry.py and response_executor.py."""

from backend.response_engine.response_executor import execute_actions
from backend.response_engine.response_registry import ResponseContext, get_handler, get_rollback_action, list_actions


def make_context(mode="simulation") -> ResponseContext:
    return ResponseContext(
        alert_id="a1", severity="Critical", attack_type="DoS",
        source_ip="10.0.0.1", destination_ip="10.0.0.2", flow_id="f1", mode=mode,
    )


def test_all_spec_required_actions_are_registered():
    required = {
        "block_ip", "unblock_ip", "quarantine_host", "restart_service", "kill_process",
        "send_email", "send_telegram", "webhook_notification", "log_response",
    }
    assert required.issubset(set(list_actions()))


def test_block_ip_rolls_back_to_unblock_ip():
    assert get_rollback_action("block_ip") == "unblock_ip"


def test_quarantine_host_rolls_back_to_unquarantine_host():
    assert get_rollback_action("quarantine_host") == "unquarantine_host"


def test_actions_without_rollback_have_none():
    assert get_rollback_action("send_email") is None
    assert get_rollback_action("restart_service") is None


def test_execute_actions_runs_every_action_in_order():
    results = execute_actions(["notify_analyst", "increase_monitoring"], make_context())
    assert [r.action for r in results] == ["notify_analyst", "increase_monitoring"]
    assert all(r.status == "success" for r in results)


def test_execute_actions_reports_unknown_action_as_failed_without_stopping():
    results = execute_actions(["notify_analyst", "not_a_real_action", "increase_monitoring"], make_context())
    statuses = {r.action: r.status for r in results}
    assert statuses["notify_analyst"] == "success"
    assert statuses["not_a_real_action"] == "failed"
    assert statuses["increase_monitoring"] == "success"  # execution continued past the failure


def test_execute_actions_catches_a_handler_exception_without_stopping(monkeypatch):
    def broken_handler(context):
        raise RuntimeError("boom")

    from backend.response_engine import response_registry
    response_registry.register_action("broken_action_for_test", broken_handler)

    results = execute_actions(["broken_action_for_test", "notify_analyst"], make_context())
    assert results[0].status == "failed"
    assert "boom" in results[0].message
    assert results[1].status == "success"


def test_every_action_result_has_execution_time_recorded():
    results = execute_actions(["notify_analyst"], make_context())
    assert results[0].execution_time_ms >= 0.0
