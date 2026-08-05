"""Tests for alert.build_alert()."""

from backend.detection.alert import build_alert
from backend.ml.schemas import PredictionResponse
from backend.packet_capture.flow_manager import Flow


def test_build_alert_combines_flow_and_prediction():
    flow = Flow(
        flow_id="flow-123", key=("10.0.0.1", 5000, "10.0.0.2", 80, "TCP"),
        protocol="TCP", src_ip="10.0.0.1", dst_ip="10.0.0.2", src_port=5000, dst_port=80,
        start_time=1000.0, last_seen=1001.0,
    )
    prediction = PredictionResponse(
        prediction="DoS", confidence=99.2, severity="High", model_version="v1", latency_ms=4.2,
    )

    alert = build_alert(flow, prediction)

    assert alert.attack == "DoS"
    assert alert.confidence == 99.2
    assert alert.severity == "High"
    assert alert.source_ip == "10.0.0.1"
    assert alert.destination_ip == "10.0.0.2"
    assert alert.protocol == "TCP"
    assert alert.flow_id == "flow-123"
    assert alert.source_port == 5000
    assert alert.destination_port == 80
    assert alert.model_version == "v1"
    assert alert.id  # auto-generated UUID
    assert alert.timestamp  # auto-generated ISO timestamp


def test_alert_serializes_to_the_spec_shape():
    flow = Flow(
        flow_id="flow-xyz", key=("1.1.1.1", 1, "2.2.2.2", 2, "UDP"),
        protocol="UDP", src_ip="1.1.1.1", dst_ip="2.2.2.2", src_port=1, dst_port=2,
        start_time=0.0, last_seen=0.0,
    )
    prediction = PredictionResponse(
        prediction="BENIGN", confidence=88.0, severity="Low", model_version="v2", latency_ms=1.0,
    )
    alert = build_alert(flow, prediction)
    body = alert.model_dump()

    for required_key in ("id", "timestamp", "attack", "severity", "confidence", "source_ip", "destination_ip", "protocol", "flow_id"):
        assert required_key in body
