"""Tests for the policy engine: loading, evaluation, and updating."""

import pytest

from backend.response_engine.response_rules import InvalidPolicyError


def test_loads_default_policies(policy_engine):
    assert policy_engine.get_actions("Critical") == ["block_ip", "quarantine_host", "send_email", "send_telegram", "log_response"]
    assert policy_engine.get_actions("Low") == ["log_response"]


def test_defaults_to_simulation_mode(policy_engine):
    assert policy_engine.is_simulation_mode() is True


def test_unknown_severity_returns_empty_list(policy_engine):
    assert policy_engine.get_actions("Unknown") == []


def test_update_changes_policy_and_persists(policy_engine):
    policy_engine.update(policies={"Critical": ["block_ip", "log_response"]})

    assert policy_engine.get_actions("Critical") == ["block_ip", "log_response"]

    # Persisted to disk - a fresh PolicyEngine reading the same file sees it too.
    from backend.response_engine.response_rules import PolicyEngine
    reloaded = PolicyEngine(rules_path=policy_engine.rules_path)
    assert reloaded.get_actions("Critical") == ["block_ip", "log_response"]


def test_update_simulation_mode(policy_engine):
    policy_engine.update(simulation_mode=False)
    assert policy_engine.is_simulation_mode() is False


def test_update_rejects_unknown_action(policy_engine):
    with pytest.raises(InvalidPolicyError, match="not_a_real_action"):
        policy_engine.update(policies={"Critical": ["not_a_real_action"]})

    # Rejected update must not have partially applied.
    assert "not_a_real_action" not in policy_engine.get_actions("Critical")


def test_get_all_policies_returns_a_copy_not_a_live_reference(policy_engine):
    policies = policy_engine.get_all_policies()
    policies["Critical"].append("mutated")
    assert "mutated" not in policy_engine.get_actions("Critical")
