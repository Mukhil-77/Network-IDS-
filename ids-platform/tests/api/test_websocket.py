"""
Tests for WS /ws/alerts.

Milestone 9: the endpoint now requires a valid access token as a query
param (see backend/api/routes/websocket.py) - the `client` fixture
authenticates as the default admin and exposes the token as
`client.access_token` (tests/api/conftest.py) for exactly this.

Uses TestClient's real websocket_connect() (a genuine, if in-process,
WebSocket handshake) rather than testing ConnectionManager/AlertBroadcaster
in isolation for the main flow - this proves the whole path: a detection ->
AlertService -> broadcaster -> connection_manager -> the actual socket, the
same route registered in main.py.
"""

import json

from backend.detection.alert import Alert as DetectionAlert
from backend.ml.schemas import PredictionResponse
from backend.packet_capture.flow_manager import Flow
from backend.services.alert_service import AlertService
from backend.websocket.broadcaster import broadcaster


def make_flow(flow_id="flow-ws-1"):
    return Flow(
        flow_id=flow_id, key=("10.0.0.1", 5000, "10.0.0.9", 80, "TCP"),
        protocol="TCP", src_ip="10.0.0.1", dst_ip="10.0.0.9", src_port=5000, dst_port=80,
        start_time=1000.0, last_seen=1001.0,
    )


def test_alert_is_broadcast_to_connected_client(client):
    with client.websocket_connect(f"/ws/alerts?token={client.access_token}") as ws:
        flow = make_flow()
        prediction = PredictionResponse(prediction="DoS", confidence=97.5, severity="High", model_version="v1", latency_ms=3.2)
        alert = DetectionAlert(
            attack="DoS", severity="High", confidence=97.5,
            source_ip="10.0.0.1", destination_ip="10.0.0.9", protocol="TCP", flow_id=flow.flow_id,
            source_port=5000, destination_port=80, model_version="v1",
        )

        # Uses the process-wide `broadcaster`, which main.py's lifespan binds
        # to the TestClient's running event loop on `with TestClient(app)`.
        AlertService(broadcaster=broadcaster).handle_detection(alert, flow, prediction)

        raw_message = ws.receive_text()
        event = json.loads(raw_message)

        assert event["type"] == "alert"
        assert event["payload"]["attack"] == "DoS"
        assert event["payload"]["confidence"] == 97.5
        assert event["payload"]["flow_id"] == flow.flow_id
        assert "timestamp" in event


def test_multiple_clients_all_receive_the_broadcast(client):
    with client.websocket_connect(f"/ws/alerts?token={client.access_token}") as ws1, client.websocket_connect(f"/ws/alerts?token={client.access_token}") as ws2:
        flow = make_flow("flow-ws-2")
        prediction = PredictionResponse(prediction="BENIGN", confidence=60.0, severity="Low", model_version="v1", latency_ms=1.0)
        alert = DetectionAlert(
            attack="BENIGN", severity="Low", confidence=60.0,
            source_ip="10.0.0.1", destination_ip="10.0.0.9", protocol="TCP", flow_id=flow.flow_id,
            source_port=5000, destination_port=80, model_version="v1",
        )

        AlertService(broadcaster=broadcaster).handle_detection(alert, flow, prediction)

        msg1 = json.loads(ws1.receive_text())
        msg2 = json.loads(ws2.receive_text())
        assert msg1["payload"]["flow_id"] == msg2["payload"]["flow_id"] == flow.flow_id


def test_disconnecting_a_client_does_not_affect_others(client):
    with client.websocket_connect(f"/ws/alerts?token={client.access_token}") as ws1:
        with client.websocket_connect(f"/ws/alerts?token={client.access_token}"):
            pass  # connect and immediately close

        flow = make_flow("flow-ws-3")
        prediction = PredictionResponse(prediction="DoS", confidence=80.0, severity="Medium", model_version="v1", latency_ms=2.0)
        alert = DetectionAlert(
            attack="DoS", severity="Medium", confidence=80.0,
            source_ip="10.0.0.1", destination_ip="10.0.0.9", protocol="TCP", flow_id=flow.flow_id,
            source_port=5000, destination_port=80, model_version="v1",
        )
        AlertService(broadcaster=broadcaster).handle_detection(alert, flow, prediction)

        msg = json.loads(ws1.receive_text())
        assert msg["payload"]["flow_id"] == flow.flow_id
