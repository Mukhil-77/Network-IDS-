"""Tests for GET / and GET /health."""


def test_root_returns_api_info(client):
    response = client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["name"]
    assert body["version"]
    assert body["docs_url"] == "/docs"


def test_health_reports_degraded_when_no_model_loaded(client):
    response = client.get("/health")
    assert response.status_code == 200  # health check itself never errors
    body = response.json()
    assert body["status"] == "degraded"
    assert body["model_status"] == "unavailable"
    assert "version" in body
    assert body["uptime_seconds"] >= 0


def test_health_reports_healthy_when_model_loaded(client_with_model):
    response = client_with_model.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["model_status"] == "loaded"


def test_health_response_has_request_id_and_timing_headers(client):
    response = client.get("/health")
    assert "X-Request-ID" in response.headers
    assert "X-Process-Time-Ms" in response.headers
