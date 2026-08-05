"""
Live packet capture.

Two interchangeable backends (see interface.CaptureBackend):

    ScapyCaptureBackend   - uses scapy.AsyncSniffer, which already runs
                             capture on its own background thread.
    PySharkCaptureBackend - uses pyshark.LiveCapture (a tshark wrapper);
                             imported lazily since pyshark requires the
                             `tshark` binary to be installed, which won't
                             be true in every environment this code runs
                             in (e.g. this project's test/dev sandbox).

`PacketCapture` is the orchestrator: it owns a backend + a FlowManager and
wires "raw packet in" -> packet_parser.parse_packet() -> flow_manager.add_packet()
so nothing above this module ever touches a raw scapy/pyshark object.
"""

from __future__ import annotations

from typing import Optional

from backend.packet_capture.flow_manager import FlowManager
from backend.packet_capture.interface import CaptureBackend, RawPacketCallback
from backend.packet_capture.packet_filter import PacketFilterConfig, build_bpf_filter
from backend.packet_capture.packet_parser import parse_packet
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class ScapyCaptureBackend:
    """CaptureBackend implementation using scapy.AsyncSniffer."""

    def __init__(self, interface: Optional[str], bpf_filter: str):
        self.interface = interface
        self.bpf_filter = bpf_filter
        self._sniffer = None

    def start(self, on_packet: RawPacketCallback) -> None:
        from scapy.all import AsyncSniffer

        self._sniffer = AsyncSniffer(
            iface=self.interface,
            filter=self.bpf_filter,
            prn=on_packet,
            store=False,  # never buffer captured packets in memory - flows are our memory
        )
        self._sniffer.start()

    def stop(self) -> None:
        if self._sniffer is not None:
            self._sniffer.stop()
            self._sniffer = None


class PySharkCaptureBackend:
    """
    CaptureBackend implementation using pyshark.LiveCapture.

    Requires both the `pyshark` package and the `tshark` binary to be
    installed on the host - neither is assumed to be present, so the
    import happens inside start(), not at module load time. This means
    importing backend.packet_capture.capture never fails just because
    PyShark/tshark aren't installed; only actually starting this specific
    backend does.
    """

    def __init__(self, interface: str, bpf_filter: str):
        self.interface = interface
        self.bpf_filter = bpf_filter
        self._capture = None
        self._thread = None

    def start(self, on_packet: RawPacketCallback) -> None:
        import threading

        try:
            import pyshark
        except ImportError as exc:
            raise RuntimeError(
                "PySharkCaptureBackend requires the 'pyshark' package and the 'tshark' "
                "binary. Install both, or use ScapyCaptureBackend instead."
            ) from exc

        self._capture = pyshark.LiveCapture(interface=self.interface, bpf_filter=self.bpf_filter)

        def _run():
            for packet in self._capture.sniff_continuously():
                on_packet(packet)

        self._thread = threading.Thread(target=_run, name="pyshark-capture", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._capture is not None:
            self._capture.close()
            self._capture = None


class PacketCapture:
    """
    Orchestrates one capture session: backend -> packet_parser -> flow_manager.

    Usage:
        flow_manager = FlowManager(on_flow_closed=detection_service.handle_flow)
        capture = PacketCapture(interface="eth0", flow_manager=flow_manager)
        capture.start()
        ...
        capture.stop()
    """

    def __init__(
        self,
        flow_manager: FlowManager,
        interface: Optional[str] = None,
        backend: str = "scapy",
        filter_config: Optional[PacketFilterConfig] = None,
    ):
        if backend not in ("scapy", "pyshark"):
            raise ValueError(f"Unknown capture backend '{backend}'; expected 'scapy' or 'pyshark'")

        self.flow_manager = flow_manager
        self.interface = interface
        self.bpf_filter = build_bpf_filter(filter_config)
        self._backend: CaptureBackend = (
            ScapyCaptureBackend(interface, self.bpf_filter)
            if backend == "scapy"
            else PySharkCaptureBackend(interface, self.bpf_filter)
        )
        self._running = False
        self.packet_count = 0

    def _handle_raw_packet(self, raw_packet: object) -> None:
        self.packet_count += 1
        parsed = parse_packet(raw_packet)
        if parsed is not None:
            self.flow_manager.add_packet(parsed)

    def start(self) -> None:
        if self._running:
            return
        self.flow_manager.start()
        self._backend.start(self._handle_raw_packet)
        self._running = True
        logger.info("Packet capture started (interface=%s, filter='%s')", self.interface or "default", self.bpf_filter)

    def stop(self) -> None:
        if not self._running:
            return
        self._backend.stop()
        self.flow_manager.stop()
        self._running = False
        logger.info("Packet capture stopped")
