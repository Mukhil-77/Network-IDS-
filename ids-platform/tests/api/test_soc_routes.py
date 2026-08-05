"""
Tests for the Milestone 6 SOC REST endpoints.

Uses the `client`/`client_with_model` fixtures from tests/api/conftest.py,
which back every request with an isolated SQLite DB - test data is seeded
directly through AlertService.handle_detection() (the same path a real
detection takes) rather than inserted via raw SQL, so these tests exercise
the real persistence code, not a shortcut around it.
"""

from datetime import datetime, timezone

import pytest

from backend.detection.alert import Alert as DetectionAlert
from backend.ml.schemas import PredictionResponse
from backend.packet_capture.flow_manager import Flow
from backend.services.alert_service import AlertService
from backend.websocket.broadcaster import AlertBroadcaster
from backend.websocket.manager import ConnectionManager


def seed_detection(attack="DoS", severity="High", confidence=95.0, source_ip="10.0.0.1", flow_id=None):
    """Push one detection through the real AlertService (no WebSocket wiring needed for these tests)."""
    flow_id = flow_id or f"flow-{source_ip}-{attack}"
    flow = Flow(
        flow_id=flow_id, key=(source_ip, 5000, "10.0.0.9", 80, "TCP"),
        protocol="TCP", src_ip=source_ip, dst_ip="10.0.0.9", src_port=5000, dst_port=80,
        start_time=1000.0, last_seen=1001.0,
    )
    flow.fwd_lengths = [100, 100]
    flow.bwd_lengths = [200]

    prediction = PredictionResponse(prediction=attack, confidence=confidence, severity=severity, model_version="v1", latency_ms=4.5)
    alert = DetectionAlert(
        attack=attack, severity=severity, confidence=confidence,
        source_ip=source_ip, destination_ip="10.0.0.9", protocol="TCP", flow_id=flow_id,
        source_port=5000, destination_port=80, model_version="v1",
    )

    # A broadcaster with no bound event loop just no-ops (logged), so this
    # is safe to call outside a running app/event loop.
    service = AlertService(broadcaster=AlertBroadcaster(ConnectionManager()))
    service.handle_detection(alert, flow, prediction)
    return alert


class TestAlertsEndpoints:
    def test_list_alerts_empty(self, client):
        response = client.get("/alerts")
        assert response.status_code == 200
        assert response.json() == {"items": [], "total": 0, "page": 1, "page_size": 50}

    def test_list_alerts_returns_seeded_data(self, client):
        seed_detection(attack="DoS")
        seed_detection(attack="PortScan")

        response = client.get("/alerts")
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 2
        assert len(body["items"]) == 2

    def test_filter_by_attack_type(self, client):
        seed_detection(attack="DoS")
        seed_detection(attack="PortScan")

        response = client.get("/alerts", params={"attack_type": "DoS"})
        body = response.json()
        assert body["total"] == 1
        assert body["items"][0]["attack_type"] == "DoS"

    def test_filter_by_severity_and_min_confidence(self, client):
        seed_detection(severity="High", confidence=95.0, flow_id="f1")
        seed_detection(severity="High", confidence=40.0, flow_id="f2")

        response = client.get("/alerts", params={"severity": "High", "min_confidence": 90.0})
        body = response.json()
        assert body["total"] == 1
        assert body["items"][0]["confidence"] == 95.0

    def test_filter_by_source_ip(self, client):
        seed_detection(source_ip="1.1.1.1", flow_id="f1")
        seed_detection(source_ip="2.2.2.2", flow_id="f2")

        response = client.get("/alerts", params={"source_ip": "1.1.1.1"})
        assert response.json()["total"] == 1

    def test_pagination(self, client):
        for i in range(5):
            seed_detection(flow_id=f"f{i}")

        response = client.get("/alerts", params={"page": 1, "page_size": 2})
        body = response.json()
        assert body["total"] == 5
        assert len(body["items"]) == 2

    def test_sorting_by_confidence(self, client):
        seed_detection(confidence=30.0, flow_id="f1")
        seed_detection(confidence=90.0, flow_id="f2")

        response = client.get("/alerts", params={"sort_by": "confidence", "sort_desc": True})
        assert response.json()["items"][0]["confidence"] == 90.0

    def test_get_alert_by_id(self, client):
        alert = seed_detection()
        response = client.get(f"/alerts/{alert.id}")
        assert response.status_code == 200
        assert response.json()["id"] == alert.id

    def test_get_alert_404_for_unknown_id(self, client):
        response = client.get("/alerts/does-not-exist")
        assert response.status_code == 404

    def test_latest_alerts(self, client):
        seed_detection(flow_id="f1")
        seed_detection(flow_id="f2")

        response = client.get("/alerts/latest", params={"limit": 1})
        assert response.status_code == 200
        assert len(response.json()) == 1


class TestFlowsEndpoint:
    def test_list_flows_returns_seeded_flow(self, client):
        seed_detection()
        response = client.get("/flows")
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["items"][0]["protocol"] == "TCP"

    def test_filter_flows_by_protocol(self, client):
        seed_detection()
        response = client.get("/flows", params={"protocol": "UDP"})
        assert response.json()["total"] == 0


class TestStatisticsEndpoint:
    def test_statistics_reflects_seeded_alerts(self, client):
        seed_detection(attack="DoS", severity="High", flow_id="f1")
        seed_detection(attack="DoS", severity="High", flow_id="f2")

        response = client.get("/statistics")
        assert response.status_code == 200
        body = response.json()
        assert body["threat_count"] == 2
        assert body["threats_by_type"] == {"DoS": 2}
        assert body["threats_by_severity"] == {"High": 2}
        assert body["average_prediction_latency_ms"] == pytest.approx(4.5)

    def test_statistics_detection_accuracy_reflects_model_metadata(self, client_with_model):
        # client_with_model's lifespan syncs the fixture model's metadata to
        # the DB at startup (see main.py's _sync_model_metadata_to_db).
        response = client_with_model.get("/statistics")
        assert response.status_code == 200
        assert response.json()["detection_accuracy"] is not None


class TestAttacksTopEndpoint:
    def test_top_attacks_sorted_by_frequency(self, client):
        seed_detection(attack="DoS", flow_id="f1")
        seed_detection(attack="DoS", flow_id="f2")
        seed_detection(attack="PortScan", flow_id="f3")

        response = client.get("/attacks/top")
        assert response.status_code == 200
        body = response.json()
        assert body[0]["attack_type"] == "DoS"
        assert body[0]["total_count"] == 2


class TestSystemHealthEndpoint:
    def test_system_health_degraded_without_model(self, client):
        response = client.get("/system/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "degraded"
        assert body["model_status"] == "unavailable"

    def test_system_health_healthy_with_model(self, client_with_model):
        response = client_with_model.get("/system/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_system_health_reflects_recent_alert_count(self, client):
        seed_detection()
        response = client.get("/system/health")
        assert response.json()["alerts_last_minute"] == 1
