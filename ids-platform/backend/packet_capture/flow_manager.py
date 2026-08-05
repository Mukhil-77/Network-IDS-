"""
Packet -> Flow.

A "flow" here means what CICFlowMeter (the tool that produced CIC-IDS2017)
means: all packets sharing the same (src IP, src port, dst IP, dst port,
protocol) 5-tuple, in either direction, from the first packet until the
flow is closed. "Forward" is the direction of the first packet seen;
"backward" is the reverse.

Thread-safety: a single `threading.RLock` guards all reads/writes to the
flow table. Per-flow updates are a handful of list appends and a counter
increment - fast enough that one coarse-grained lock is simpler and just
as fast as per-flow locking at the packet rates this project targets. If
throughput ever becomes a bottleneck, that's the one place to revisit.
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Callable, Optional

from backend.packet_capture.packet_parser import ParsedPacket
from backend.utils.logger import get_logger

logger = get_logger(__name__)

# Matches CICFlowMeter's default flow activity timeout (120s of inactivity closes a flow).
DEFAULT_IDLE_TIMEOUT_SECONDS = 120.0
# Safety valve so a long-lived connection (e.g. an idle SSH session) can't
# hold a flow open forever and never get classified.
DEFAULT_MAX_FLOW_DURATION_SECONDS = 600.0
# How often the background thread scans for flows to close.
DEFAULT_TIMEOUT_CHECK_INTERVAL_SECONDS = 5.0

FlowKey = tuple[str, int, str, int, str]  # normalized, direction-agnostic


def _flow_key(pkt: ParsedPacket) -> FlowKey:
    """Direction-agnostic key: both directions of one connection map to the same flow."""
    a = (pkt.src_ip, pkt.src_port)
    b = (pkt.dst_ip, pkt.dst_port)
    lo, hi = sorted([a, b])
    return (lo[0], lo[1], hi[0], hi[1], pkt.protocol)


# Optional per-packet hook (capture_service.py subscribes to broadcast a live
# packet feed over WebSocket). Receives the parsed packet, not the raw frame.
PacketIngestedCallback = Callable[[ParsedPacket], None]


@dataclass
class Flow:
    """
    One in-progress or completed network flow. Mirrors the fields the spec
    asks for (source/dest IP/port, protocol, start/end time, packet/byte
    count) plus the raw per-packet history flow_features.py needs to
    compute the fuller CIC-IDS2017-style feature set.
    """

    flow_id: str
    key: FlowKey
    protocol: str
    src_ip: str  # forward direction = direction of the first packet
    dst_ip: str
    src_port: int
    dst_port: int
    start_time: float
    last_seen: float = 0.0

    fwd_lengths: list[int] = field(default_factory=list)
    bwd_lengths: list[int] = field(default_factory=list)
    fwd_timestamps: list[float] = field(default_factory=list)
    bwd_timestamps: list[float] = field(default_factory=list)
    fwd_header_bytes: int = 0
    bwd_header_bytes: int = 0

    flag_counts: dict[str, int] = field(
        default_factory=lambda: {"FIN": 0, "SYN": 0, "RST": 0, "PSH": 0, "ACK": 0, "URG": 0}
    )
    fwd_psh: int = 0
    bwd_psh: int = 0
    fwd_urg: int = 0
    bwd_urg: int = 0

    @property
    def packet_count(self) -> int:
        return len(self.fwd_lengths) + len(self.bwd_lengths)

    @property
    def byte_count(self) -> int:
        return sum(self.fwd_lengths) + sum(self.bwd_lengths)

    def add_packet(self, pkt: ParsedPacket) -> None:
        is_forward = (pkt.src_ip, pkt.src_port) == (self.src_ip, self.src_port)

        if is_forward:
            self.fwd_lengths.append(pkt.length)
            self.fwd_timestamps.append(pkt.timestamp)
            self.fwd_header_bytes += pkt.header_length
            if "PSH" in pkt.tcp_flags:
                self.fwd_psh += 1
            if "URG" in pkt.tcp_flags:
                self.fwd_urg += 1
        else:
            self.bwd_lengths.append(pkt.length)
            self.bwd_timestamps.append(pkt.timestamp)
            self.bwd_header_bytes += pkt.header_length
            if "PSH" in pkt.tcp_flags:
                self.bwd_psh += 1
            if "URG" in pkt.tcp_flags:
                self.bwd_urg += 1

        for flag in pkt.tcp_flags:
            self.flag_counts[flag] = self.flag_counts.get(flag, 0) + 1

        self.last_seen = max(self.last_seen, pkt.timestamp)

    def saw_terminal_flag(self) -> bool:
        """True once a FIN or RST has been observed - such a flow should close promptly rather than wait out the idle timeout."""
        return self.flag_counts.get("FIN", 0) > 0 or self.flag_counts.get("RST", 0) > 0


FlowClosedCallback = Callable[[Flow], None]


class FlowManager:
    """
    Owns the live flow table. capture.py feeds it parsed packets via
    `add_packet()`; a background thread closes idle/terminated/over-duration
    flows and invokes `on_flow_closed` for each one - detection_service.py
    is the intended subscriber, but FlowManager has no dependency on it.
    """

    def __init__(
        self,
        on_flow_closed: Optional[FlowClosedCallback] = None,
        on_packet: Optional[PacketIngestedCallback] = None,
        idle_timeout_seconds: float = DEFAULT_IDLE_TIMEOUT_SECONDS,
        max_flow_duration_seconds: float = DEFAULT_MAX_FLOW_DURATION_SECONDS,
        check_interval_seconds: float = DEFAULT_TIMEOUT_CHECK_INTERVAL_SECONDS,
    ):
        self.on_flow_closed = on_flow_closed
        self.on_packet = on_packet
        self.idle_timeout_seconds = idle_timeout_seconds
        self.max_flow_duration_seconds = max_flow_duration_seconds
        self.check_interval_seconds = check_interval_seconds

        self._flows: dict[FlowKey, Flow] = {}
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._timeout_thread: Optional[threading.Thread] = None

    # ---------------------------------------------------------------- #
    # Packet ingestion
    # ---------------------------------------------------------------- #

    def add_packet(self, pkt: ParsedPacket) -> Flow:
        """Route one parsed packet to its flow, creating a new flow if none exists yet. Thread-safe."""
        key = _flow_key(pkt)
        close_now: Optional[Flow] = None

        with self._lock:
            flow = self._flows.get(key)
            if flow is None:
                flow = Flow(
                    flow_id=str(uuid.uuid4()),
                    key=key,
                    protocol=pkt.protocol,
                    src_ip=pkt.src_ip,
                    dst_ip=pkt.dst_ip,
                    src_port=pkt.src_port,
                    dst_port=pkt.dst_port,
                    start_time=pkt.timestamp,
                )
                self._flows[key] = flow
                logger.info("New flow: %s %s:%d <-> %s:%d", flow.protocol, flow.src_ip, flow.src_port, flow.dst_ip, flow.dst_port)

            flow.add_packet(pkt)

            if flow.protocol == "TCP" and flow.saw_terminal_flag():
                close_now = self._flows.pop(key, None)

        if close_now is not None:
            self._close(close_now, reason="FIN/RST observed")

        if self.on_packet is not None:
            try:
                self.on_packet(pkt)
            except Exception:  # noqa: BLE001 - a subscriber's bug must never break packet/flow handling
                logger.exception("on_packet callback raised")

        return flow

    # ---------------------------------------------------------------- #
    # Idle/expired flow reaping
    # ---------------------------------------------------------------- #

    def start(self) -> None:
        """Start the background thread that closes idle/expired flows. No-op if already running."""
        if self._timeout_thread is not None and self._timeout_thread.is_alive():
            return
        self._stop_event.clear()
        self._timeout_thread = threading.Thread(target=self._timeout_loop, name="flow-timeout-checker", daemon=True)
        self._timeout_thread.start()
        logger.info("FlowManager timeout checker started (idle_timeout=%.0fs)", self.idle_timeout_seconds)

    def stop(self) -> None:
        """Stop the background thread and close every remaining open flow."""
        self._stop_event.set()
        if self._timeout_thread is not None:
            self._timeout_thread.join(timeout=self.check_interval_seconds + 1)
        self.close_all()
        logger.info("FlowManager timeout checker stopped")

    def _timeout_loop(self) -> None:
        while not self._stop_event.wait(self.check_interval_seconds):
            self._reap_expired_flows()

    def _reap_expired_flows(self) -> None:
        now = time.time()
        expired: list[Flow] = []

        with self._lock:
            for key in list(self._flows.keys()):
                flow = self._flows[key]
                idle_for = now - flow.last_seen
                duration = now - flow.start_time
                if idle_for >= self.idle_timeout_seconds or duration >= self.max_flow_duration_seconds:
                    expired.append(self._flows.pop(key))

        for flow in expired:
            reason = "idle timeout" if (now - flow.last_seen) >= self.idle_timeout_seconds else "max duration reached"
            self._close(flow, reason=reason)

    def close_all(self) -> None:
        """Force-close every open flow (e.g. on shutdown), so nothing captured is silently discarded."""
        with self._lock:
            remaining = list(self._flows.values())
            self._flows.clear()
        for flow in remaining:
            self._close(flow, reason="manager shutdown")

    def _close(self, flow: Flow, reason: str) -> None:
        logger.info(
            "Flow closed (%s): %s %s:%d <-> %s:%d, packets=%d, bytes=%d",
            reason, flow.protocol, flow.src_ip, flow.src_port, flow.dst_ip, flow.dst_port,
            flow.packet_count, flow.byte_count,
        )
        if self.on_flow_closed is not None:
            try:
                self.on_flow_closed(flow)
            except Exception:  # noqa: BLE001 - a subscriber's bug must never break flow management
                logger.exception("on_flow_closed callback raised for flow %s", flow.flow_id)

    # ---------------------------------------------------------------- #
    # Introspection (for /health-style visibility in a later milestone)
    # ---------------------------------------------------------------- #

    def active_flow_count(self) -> int:
        with self._lock:
            return len(self._flows)
