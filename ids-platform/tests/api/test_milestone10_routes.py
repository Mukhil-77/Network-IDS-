"""API tests for Milestone 10: /reports, /analytics, /threat-intelligence, /incidents, /notifications/test."""

import pytest


class TestReportsEndpoints:
    def test_list_reports_returns_every_type(self, client):
        response = client.get("/reports")
        assert response.status_code == 200
        types = {r["report_type"] for r in response.json()}
        assert types == {"daily", "weekly", "monthly", "custom", "incident", "threat_summary", "executive_summary"}

    def test_generate_json_report(self, client):
        response = client.post("/reports/generate", json={"report_type": "daily", "format": "json"})
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"

    def test_generate_csv_report(self, client):
        response = client.post("/reports/generate", json={"report_type": "weekly", "format": "csv"})
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/csv")

    def test_generate_pdf_report(self, client):
        response = client.post("/reports/generate", json={"report_type": "monthly", "format": "pdf"})
        assert response.status_code == 200
        assert response.content.startswith(b"%PDF")

    def test_generate_unknown_report_type_returns_400(self, client):
        response = client.post("/reports/generate", json={"report_type": "not_a_type", "format": "json"})
        assert response.status_code == 400

    def test_generate_unknown_format_returns_400(self, client):
        response = client.post("/reports/generate", json={"report_type": "daily", "format": "xml"})
        assert response.status_code == 400

    def test_generate_incident_report_without_id_returns_400(self, client):
        response = client.post("/reports/generate", json={"report_type": "incident", "format": "json"})
        assert response.status_code == 400


class TestAnalyticsEndpoints:
    def test_analytics_overview(self, client):
        response = client.get("/analytics")
        assert response.status_code == 200
        body = response.json()
        assert "top_attack_types" in body
        assert body["false_positive_rate"] is None  # honest placeholder

    def test_analytics_trends(self, client):
        # Seed one alert so there's a timeline point to forecast from -
        # forecast_next_days([]) correctly returns [] with no data (see
        # tests/analytics/test_forecasting.py), which isn't what this test
        # is checking.
        client.post("/incidents", json={"title": "seed", "severity": "Low"})  # cheap way to ensure the DB/session works; alert seeding below is what matters
        import backend.database.connection as connection_module
        from datetime import datetime, timezone
        from backend.database.models import Alert, FlowHistory
        with connection_module.SessionLocal() as db:
            db.add(FlowHistory(
                id="f-trend", protocol="TCP", source_ip="10.0.0.1", destination_ip="10.0.0.9",
                source_port=1, destination_port=2, start_time=datetime.now(timezone.utc), end_time=datetime.now(timezone.utc),
                packet_count=1, byte_count=1,
            ))
            db.add(Alert(
                id="a-trend", attack_type="DoS", confidence=90.0, severity="High",
                source_ip="10.0.0.1", destination_ip="10.0.0.9", protocol="TCP", flow_id="f-trend",
                packet_count=1, bytes=1, status="new", model_version="v1", processing_time_ms=1.0,
            ))
            db.commit()

        response = client.get("/analytics/trends", params={"forecast_days": 5})
        assert response.status_code == 200
        assert len(response.json()["forecast"]) == 5


class TestThreatIntelligenceEndpoint:
    def test_list_indicators_includes_seeded_demo_data(self, client):
        # main.py's lifespan syncs the bundled demo feed at every startup.
        response = client.get("/threat-intelligence")
        assert response.status_code == 200
        values = {i["value"] for i in response.json()}
        assert "198.51.100.23" in values

    def test_filter_by_tag(self, client):
        response = client.get("/threat-intelligence", params={"tag": "Known Malicious"})
        assert response.status_code == 200
        assert all(i["tag"] == "Known Malicious" for i in response.json())


class TestIncidentsEndpoints:
    def test_create_and_list_incident(self, client):
        create_response = client.post("/incidents", json={"title": "Suspicious login", "severity": "High"})
        assert create_response.status_code == 201
        assert create_response.json()["status"] == "open"
        assert create_response.json()["created_by"] == "admin"

        list_response = client.get("/incidents")
        assert list_response.status_code == 200
        assert list_response.json()["total"] == 1

    def test_update_incident_status_and_owner(self, client):
        incident_id = client.post("/incidents", json={"title": "Test", "severity": "Medium"}).json()["id"]

        response = client.put(f"/incidents/{incident_id}", json={"status": "assigned", "owner": "analyst1"})
        assert response.status_code == 200
        assert response.json()["status"] == "assigned"
        assert response.json()["owner"] == "analyst1"
        assert len(response.json()["timeline"]) >= 2  # created + status_changed/assigned

    def test_invalid_transition_returns_400(self, client):
        incident_id = client.post("/incidents", json={"title": "Test", "severity": "Low"}).json()["id"]
        client.put(f"/incidents/{incident_id}", json={"status": "closed"})

        response = client.put(f"/incidents/{incident_id}", json={"status": "open"})
        assert response.status_code == 400

    def test_update_unknown_incident_returns_404(self, client):
        response = client.put("/incidents/does-not-exist", json={"status": "assigned"})
        assert response.status_code == 404

    def test_filter_incidents_by_status(self, client):
        client.post("/incidents", json={"title": "A", "severity": "High"})
        second_id = client.post("/incidents", json={"title": "B", "severity": "Low"}).json()["id"]
        client.put(f"/incidents/{second_id}", json={"status": "closed"})

        response = client.get("/incidents", params={"status": "closed"})
        assert response.json()["total"] == 1


class TestNotificationTestEndpoint:
    def test_test_notification_for_low_severity_uses_dashboard_only(self, client):
        response = client.post("/notifications/test", json={"severity": "Low"})
        assert response.status_code == 200
        assert response.json()["channels_attempted"] == ["dashboard"]

    def test_test_notification_for_critical_attempts_all_three_channels(self, client):
        response = client.post("/notifications/test", json={"severity": "Critical"})
        assert response.status_code == 200
        assert set(response.json()["channels_attempted"]) == {"email", "telegram", "webhook"}


class TestPermissionEnforcement:
    def _register_viewer(self, client):
        client.post("/auth/register", json={"username": "viewer_m10", "email": "v10@example.com", "password": "Passw0rd123", "role": "Viewer"})
        token = client.post("/auth/login", json={"username": "viewer_m10", "password": "Passw0rd123"}).json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    def test_viewer_can_read_but_not_write_incidents(self, unauthenticated_client):
        headers = self._register_viewer(unauthenticated_client)
        assert unauthenticated_client.get("/incidents", headers=headers).status_code == 200
        assert unauthenticated_client.post("/incidents", json={"title": "x", "severity": "Low"}, headers=headers).status_code == 403

    def test_viewer_cannot_generate_reports(self, unauthenticated_client):
        headers = self._register_viewer(unauthenticated_client)
        assert unauthenticated_client.get("/reports", headers=headers).status_code == 200
        assert unauthenticated_client.post("/reports/generate", json={"report_type": "daily", "format": "json"}, headers=headers).status_code == 403
