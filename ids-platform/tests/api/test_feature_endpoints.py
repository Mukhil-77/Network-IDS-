"""
Tests for the Milestone-11+ feature endpoints: model train/delete/status,
flows summary, notification rules/settings, and the extended capture status.

These keep the ad-hoc verification of the new endpoints durable in the suite.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


class TestModelManagement:
    def test_train_status_is_idle_by_default(self, client):
        response = client.get("/model/train/status")
        assert response.status_code == 200
        body = response.json()
        assert body["training"] is False
        assert body["algorithm"] is None
        assert body["error"] is None
        assert body["cancelled"] is False

    def test_cancel_with_nothing_training_is_idempotent(self, client):
        response = client.post("/model/train/cancel")
        assert response.status_code == 200
        body = response.json()
        assert body["training"] is False
        assert body["cancelled"] is False

    def test_train_rejects_unknown_algorithm(self, client):
        response = client.post("/model/train", json={"algorithm": "nonsense"})
        assert response.status_code == 400

    def test_train_accepts_all_alias(self, client, monkeypatch):
        import backend.api.routes.model as model_route

        started = {}
        monkeypatch.setattr(
            model_route.prediction_service,
            "train_model",
            lambda algorithm: started.update(algorithm=algorithm) or True,
        )
        response = client.post("/model/train", json={"algorithm": "all"})
        assert response.status_code == 202
        assert started["algorithm"] == "all"

    def test_delete_unknown_version_returns_404(self, client):
        response = client.delete("/model/v999")
        assert response.status_code == 404

    def test_delete_requires_permission(self, unauthenticated_client):
        # Admin-only action; a token-less request must be rejected.
        assert unauthenticated_client.delete("/model/v1").status_code == 401


class TestInterfaceListing:
    def test_interfaces_return_structured_entries(self, client, monkeypatch):
        import backend.api.routes.capture as capture_route

        monkeypatch.setattr(
            capture_route,
            "network_interfaces",
            lambda: [
                {"name": "\\Device\\NPF_{00000000-0000-0000-0000-000000000000}", "description": "Fake Adapter · NPF_0000"},
            ],
        )
        response = client.get("/capture/interfaces")
        assert response.status_code == 200
        entries = response.json()
        assert isinstance(entries, list) and len(entries) == 1
        assert {"name", "description"} == set(entries[0])
        assert entries[0]["name"].startswith("\\Device\\NPF_")

    def test_friendly_name_keeps_readable_label(self):
        from backend.packet_capture.interface import friendly_name

        friendly = friendly_name("\\Device\\NPF_{00000000-0000-0000-0000-000000000000}")
        assert friendly.startswith("Network adapter") or "NPF_" in friendly


class TestFlowSummary:
    def test_flow_summary_shape(self, client):
        response = client.get("/flows/summary")
        assert response.status_code == 200
        body = response.json()
        for key in ("total_flows", "total_packets", "total_bytes", "per_protocol", "top_talkers"):
            assert key in body
        assert isinstance(body["per_protocol"], dict)
        assert isinstance(body["top_talkers"], list)


class TestCaptureStatus:
    def test_status_reports_session_fields(self, client):
        response = client.get("/capture/status")
        assert response.status_code == 200
        body = response.json()
        assert body["running"] is False
        assert body["protocols"] is None
        assert body["predictions_count"] == 0
        assert body["average_prediction_latency_ms"] == 0.0


class TestCaptureProtocols:
    def test_all_protocols_drops_the_transport_filter(self, client, monkeypatch):
        import backend.api.routes.capture as capture_route

        captured = {}
        monkeypatch.setattr(
            capture_route.capture_service,
            "start_capture",
            lambda **kw: captured.update(kw),
        )
        response = client.post("/capture/start", json={"protocols": ["all"]})
        assert response.status_code == 200
        assert captured["filter_config"].protocols == ()
        assert response.json()["bpf_filter"] == "(ip or ip6)"

    def test_unknown_protocol_rejected_even_with_all_mixed(self, client):
        response = client.post("/capture/start", json={"protocols": ["all", "carrier-pigeon"]})
        assert response.status_code == 400


class TestNotificationRules:
    def test_get_rules_returns_map(self, client):
        response = client.get("/notifications/rules")
        assert response.status_code == 200
        body = response.json()
        assert isinstance(body, dict)

    def test_put_rules_validates_channels(self, client):
        response = client.put("/notifications/rules", json={"rules": {"Critical": ["email", "carrier-pigeon"]}})
        assert response.status_code == 400

    def test_put_rules_round_trips(self, client, monkeypatch, tmp_path):
        from backend.notifications import notification_manager

        manager = notification_manager.notification_manager
        monkeypatch.setattr(manager, "rules_path", tmp_path / "rules.yaml")
        try:
            response = client.put("/notifications/rules", json={"rules": {"Critical": ["email", "webhook"], "Low": ["dashboard"]}})
            assert response.status_code == 200
            assert response.json()["Critical"] == ["email", "webhook"]
            assert response.json()["Low"] == ["dashboard"]
        finally:
            # Restore the process-wide manager's in-memory rules from its
            # real config file so this test can't leak state into others.
            manager.rules_path = notification_manager.DEFAULT_RULES_PATH
            manager._load()


class TestNotificationSettings:
    def test_get_settings_shape(self, client):
        response = client.get("/notifications/settings")
        assert response.status_code == 200
        body = response.json()
        assert {"email", "telegram", "webhook"} <= set(body)

    def test_put_settings_persists_to_runtime_store(self, client, monkeypatch, tmp_path):
        from backend.notifications import channel_settings

        store_path = tmp_path / "channel_settings.json"
        monkeypatch.setattr(channel_settings, "DEFAULT_SETTINGS_PATH", store_path)
        monkeypatch.setattr(channel_settings, "_cache", None)

        response = client.put(
            "/notifications/settings",
            json={"webhook": {"url": "https://example.com/hook"}},
        )
        assert response.status_code == 200
        assert response.json()["webhook"]["url"] == "https://example.com/hook"

        saved = json.loads(store_path.read_text())
        assert saved["webhook"]["url"] == "https://example.com/hook"

        # Environment fallbacks are still merged in for other channels.
        assert "email" in response.json()

    def test_put_settings_rejects_unknown_key(self, client):
        response = client.put(
            "/notifications/settings",
            json={"telegram": {"carrier_pigeon": "123"}},
        )
        assert response.status_code == 400


class TestFlowSummaryRequiresAuth:
    def test_summary_requires_permission(self, unauthenticated_client):
        assert unauthenticated_client.get("/flows/summary").status_code == 401