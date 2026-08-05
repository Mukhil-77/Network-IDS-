"""Tests for DetectionService."""

import time

from backend.detection.detection_service import DetectionService
from backend.packet_capture.flow_manager import Flow
from backend.packet_capture.packet_parser import ParsedPacket


def make_flow(flow_id="flow-1", src_port=5000) -> Flow:
    flow = Flow(
        flow_id=flow_id, key=("10.0.0.1", src_port, "10.0.0.2", 80, "TCP"),
        protocol="TCP", src_ip="10.0.0.1", dst_ip="10.0.0.2", src_port=src_port, dst_port=80,
        start_time=1000.0, last_seen=1000.0,
    )
    flow.add_packet(ParsedPacket(
        timestamp=1000.0, src_ip="10.0.0.1", dst_ip="10.0.0.2", src_port=src_port, dst_port=80,
        protocol="TCP", length=100, header_length=40, payload_length=60, tcp_flags=frozenset({"SYN"}),
    ))
    flow.last_seen = 1000.5
    return flow


def test_handle_flow_closed_returns_immediately(prediction_service_with_model):
    service = DetectionService(prediction_service=prediction_service_with_model, max_workers=2)
    try:
        start = time.perf_counter()
        service.handle_flow_closed(make_flow())
        elapsed = time.perf_counter() - start
        assert elapsed < 0.05  # submission is async; must not block on inference
    finally:
        service.shutdown()


def test_alert_is_stored_after_classification_completes(prediction_service_with_model):
    service = DetectionService(prediction_service=prediction_service_with_model, max_workers=2)
    try:
        service.handle_flow_closed(make_flow(flow_id="flow-42"))

        deadline = time.time() + 2.0
        while time.time() < deadline and not service.get_recent_alerts():
            time.sleep(0.02)

        alerts = service.get_recent_alerts()
        assert len(alerts) == 1
        assert alerts[0].flow_id == "flow-42"
    finally:
        service.shutdown()


def test_missing_model_does_not_crash_worker_or_store_alert(prediction_service_without_model):
    service = DetectionService(prediction_service=prediction_service_without_model, max_workers=2)
    try:
        service.handle_flow_closed(make_flow())
        service._executor.shutdown(wait=True)  # noqa: SLF001 - test-only: ensure the submitted job has finished
        assert service.get_recent_alerts() == []
    finally:
        pass  # executor already shut down above


def test_get_recent_alerts_respects_limit_and_ordering(prediction_service_with_model):
    service = DetectionService(prediction_service=prediction_service_with_model, max_workers=2)
    try:
        for i in range(5):
            service.handle_flow_closed(make_flow(flow_id=f"flow-{i}", src_port=5000 + i))
        service._executor.shutdown(wait=True)  # noqa: SLF001

        all_alerts = service.get_recent_alerts()
        limited = service.get_recent_alerts(limit=2)

        assert len(all_alerts) == 5
        assert len(limited) == 2
        assert limited == all_alerts[:2]  # most-recent-first
    finally:
        pass
