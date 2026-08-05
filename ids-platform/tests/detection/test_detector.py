"""Tests for Detector.classify_flow()."""

import pytest

from backend.detection.detector import Detector
from backend.ml.artifacts import ArtifactNotFoundError
from backend.packet_capture.flow_manager import Flow
from backend.packet_capture.packet_parser import ParsedPacket


def make_completed_flow() -> Flow:
    flow = Flow(
        flow_id="flow-abc", key=("10.0.0.1", 5000, "10.0.0.2", 80, "TCP"),
        protocol="TCP", src_ip="10.0.0.1", dst_ip="10.0.0.2", src_port=5000, dst_port=80,
        start_time=1000.0, last_seen=1000.0,
    )
    flow.add_packet(ParsedPacket(
        timestamp=1000.0, src_ip="10.0.0.1", dst_ip="10.0.0.2", src_port=5000, dst_port=80,
        protocol="TCP", length=100, header_length=40, payload_length=60, tcp_flags=frozenset({"SYN"}),
    ))
    flow.add_packet(ParsedPacket(
        timestamp=1001.0, src_ip="10.0.0.2", dst_ip="10.0.0.1", src_port=80, dst_port=5000,
        protocol="TCP", length=150, header_length=40, payload_length=110, tcp_flags=frozenset({"SYN", "ACK"}),
    ))
    flow.last_seen = 1001.0
    return flow


def test_classify_flow_returns_prediction_and_report(prediction_service_with_model):
    detector = Detector(prediction_service_with_model)
    flow = make_completed_flow()

    prediction, report = detector.classify_flow(flow)

    assert prediction.prediction in {"BENIGN", "DoS"}
    assert 0.0 <= prediction.confidence <= 100.0
    assert prediction.model_version == "v1"
    # The fixture model's expected features ("Feature 0".."Feature 7") don't
    # overlap with flow_features' CIC-IDS2017-style names, so every expected
    # feature is defaulted here - this is the expected, documented degraded
    # path (see feature_mapper.py), not a bug.
    assert report.coverage_ratio == 0.0
    assert len(report.filled_with_default) == 8


def test_classify_flow_raises_when_no_model_available(prediction_service_without_model):
    detector = Detector(prediction_service_without_model)
    flow = make_completed_flow()

    with pytest.raises(ArtifactNotFoundError):
        detector.classify_flow(flow)
