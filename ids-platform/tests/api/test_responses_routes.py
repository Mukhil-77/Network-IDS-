"""Tests for the Milestone 8 REST endpoints: /responses/*, /response-rules."""

import shutil
from datetime import datetime, timezone

import pytest


@pytest.fixture(autouse=True)
def isolated_policy_engine(tmp_path, monkeypatch):
    """
    PUT /response-rules persists to disk (see response_rules.py's
    docstring) - without this, running the test suite would overwrite the
    real, shipped backend/response_engine/config/response_rules.yaml.
    Points the API routes' `policy_engine` at a throwaway copy instead.
    """
    from backend.response_engine.response_rules import DEFAULT_RULES_PATH, PolicyEngine

    test_rules_path = tmp_path / "response_rules.yaml"
    shutil.copy(DEFAULT_RULES_PATH, test_rules_path)
    test_engine = PolicyEngine(rules_path=test_rules_path)

    monkeypatch.setattr("backend.api.routes.responses.policy_engine", test_engine)
    monkeypatch.setattr("backend.response_engine.response_service.default_policy_engine", test_engine)
    monkeypatch.setattr("backend.response_engine.response_service.response_service.policy_engine", test_engine)
    yield test_engine


def seed_alert(db, alert_id="a1", severity="Critical"):
    from backend.database.models import Alert, FlowHistory

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


def seed_via_api(client, severity="Critical"):
    """Seed an alert directly through the DB the client fixture already wired up."""
    import backend.database.connection as connection_module
    with connection_module.SessionLocal() as db:
        seed_alert(db, severity=severity)


class TestResponseRulesEndpoints:
    def test_get_response_rules_returns_default_policies(self, client):
        response = client.get("/response-rules")
        assert response.status_code == 200
        body = response.json()
        assert body["simulation_mode"] is True
        assert "Critical" in body["policies"]
        assert "block_ip" in body["available_actions"]

    def test_put_response_rules_updates_policy(self, client):
        response = client.put("/response-rules", json={"policies": {"Critical": ["log_response"]}})
        assert response.status_code == 200

    def test_put_response_rules_rejects_unknown_action(self, client):
        response = client.put("/response-rules", json={"policies": {"Critical": ["not_a_real_action"]}})
        assert response.status_code == 400


class TestExecuteAndListResponses:
    def test_execute_response_for_unknown_alert_returns_404(self, client):
        response = client.post("/responses/execute", json={"alert_id": "does-not-exist"})
        assert response.status_code == 404

    def test_execute_response_runs_policy_actions(self, client):
        seed_via_api(client, severity="Low")
        response = client.post("/responses/execute", json={"alert_id": "a1"})
        assert response.status_code == 200
        body = response.json()
        assert [r["action"] for r in body] == ["log_response"]

    def test_execute_response_with_explicit_actions_overrides_policy(self, client):
        seed_via_api(client, severity="Critical")
        response = client.post("/responses/execute", json={"alert_id": "a1", "actions": ["log_response"]})
        assert response.status_code == 200
        assert [r["action"] for r in response.json()] == ["log_response"]

    def test_execute_response_rejects_unknown_action(self, client):
        seed_via_api(client)
        response = client.post("/responses/execute", json={"alert_id": "a1", "actions": ["bogus"]})
        assert response.status_code == 400

    def test_list_responses_after_execution(self, client):
        seed_via_api(client, severity="Low")
        client.post("/responses/execute", json={"alert_id": "a1"})

        response = client.get("/responses")
        assert response.status_code == 200
        assert response.json()["total"] == 1

    def test_get_response_by_id(self, client):
        seed_via_api(client, severity="Low")
        created = client.post("/responses/execute", json={"alert_id": "a1"}).json()

        response = client.get(f"/responses/{created[0]['id']}")
        assert response.status_code == 200
        assert response.json()["action"] == "log_response"

    def test_get_response_404_for_unknown_id(self, client):
        response = client.get("/responses/does-not-exist")
        assert response.status_code == 404

    def test_responses_history_feed(self, client):
        seed_via_api(client, severity="Low")
        client.post("/responses/execute", json={"alert_id": "a1"})

        response = client.get("/responses/history", params={"limit": 5})
        assert response.status_code == 200
        assert len(response.json()) == 1


class TestRollback:
    def test_rollback_block_ip_action(self, client):
        seed_via_api(client, severity="Critical")
        results = client.post("/responses/execute", json={"alert_id": "a1"}).json()
        block_response = next(r for r in results if r["action"] == "block_ip")

        response = client.post("/responses/rollback", json={"response_id": block_response["id"]})
        assert response.status_code == 200
        assert response.json()["action"] == "unblock_ip"

    def test_rollback_of_unknown_response_returns_400(self, client):
        response = client.post("/responses/rollback", json={"response_id": "does-not-exist"})
        assert response.status_code == 400

    def test_rollback_of_action_without_rollback_returns_400(self, client):
        seed_via_api(client, severity="Critical")
        results = client.post("/responses/execute", json={"alert_id": "a1"}).json()
        email_response = next(r for r in results if r["action"] == "send_email")

        response = client.post("/responses/rollback", json={"response_id": email_response["id"]})
        assert response.status_code == 400
