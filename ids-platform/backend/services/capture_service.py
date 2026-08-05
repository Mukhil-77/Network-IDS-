"""
Capture orchestration service.
Manages the lifecycle of PacketCapture and wires it up to the detection pipeline.
"""
from collections import deque
from datetime import datetime, timezone
from typing import Any, Optional

from backend.detection.detection_service import DetectionService
from backend.packet_capture.capture import PacketCapture
from backend.packet_capture.flow_manager import FlowManager
from backend.packet_capture.packet_filter import PacketFilterConfig
from backend.packet_capture.packet_parser import ParsedPacket
from backend.services.alert_service import alert_service
from backend.utils.logger import get_logger
from backend.websocket.broadcaster import broadcaster
from backend.websocket.events import WSEventType

logger = get_logger(__name__)

DEFAULT_MAX_STORED_PACKETS = 500


def _packet_payload(pkt: ParsedPacket) -> dict:
    """Compact shape for the live packet feed (WSEventType.PACKET payload)."""
    return {
        "timestamp": datetime.fromtimestamp(pkt.timestamp, tz=timezone.utc).isoformat(),
        "src_ip": pkt.src_ip,
        "dst_ip": pkt.dst_ip,
        "src_port": pkt.src_port,
        "dst_port": pkt.dst_port,
        "protocol": pkt.protocol,
        "length": pkt.length,
        "flags": sorted(pkt.tcp_flags),
    }


class CaptureService:
    def __init__(self) -> None:
        # Wire detection -> alert saving/broadcasting
        self.detection_service = DetectionService(on_alert_generated=alert_service.handle_detection)

        self._recent_packets: deque[dict] = deque(maxlen=DEFAULT_MAX_STORED_PACKETS)

        # Wire flow closed -> detection, packet ingested -> live feed broadcast
        self.flow_manager = FlowManager(
            on_flow_closed=self.detection_service.handle_flow_closed,
            on_packet=self._handle_packet,
        )

        self.capture: Optional[PacketCapture] = None

    def _handle_packet(self, pkt: ParsedPacket) -> None:
        """Record one parsed packet in the bounded buffer and broadcast it live."""
        payload = _packet_payload(pkt)
        self._recent_packets.append(payload)
        broadcaster.publish_event_threadsafe(WSEventType.PACKET, payload)

    def get_recent_packets(self, limit: Optional[int] = None) -> list[dict]:
        """Most-recent-first list of packets seen by the capture pipeline."""
        packets = list(reversed(self._recent_packets))
        return packets[:limit] if limit is not None else packets

    def start_capture(
        self,
        interface: Optional[str] = None,
        backend: str = "scapy",
        filter_config: Optional[PacketFilterConfig] = None
    ) -> None:
        if self.capture is not None:
            logger.warning("Capture already running")
            return
            
        logger.info(f"Starting capture on interface {interface} with backend {backend}")
        self.capture = PacketCapture(
            flow_manager=self.flow_manager,
            interface=interface,
            backend=backend,
            filter_config=filter_config
        )
        self.capture.start()

    def stop_capture(self) -> None:
        if self.capture is not None:
            logger.info("Stopping capture")
            self.capture.stop()
            self.capture = None

    def get_status(self) -> dict[str, Any]:
        running = self.capture is not None
        
        active_flows = 0
        packet_count = 0
        if running:
            active_flows = self.flow_manager.active_flow_count()
            packet_count = getattr(self.capture, 'packet_count', 0)
            
        return {
            "running": running,
            "interface": self.capture.interface if running else None,
            "backend": self.capture._backend.__class__.__name__ if running else None,
            "active_flows": active_flows,
            "packet_count": packet_count
        }

    def shutdown(self) -> None:
        self.stop_capture()
        self.detection_service.shutdown()


capture_service = CaptureService()
