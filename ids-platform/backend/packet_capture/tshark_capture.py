"""
TShark/PyShark-based capture backend (documented path: tshark_capture.py).

A standalone PyShark capture manager with a ``live_capture()`` generator
plus a start/stop wrapper that implements the same CaptureBackend contract
as capture.py's ScapyCaptureBackend, so it can be driven by PacketCapture
(or used directly from a script for one-off capture sessions).

PyShark wraps the ``tshark`` binary; neither is assumed to be installed, so
nothing here imports pyshark at module load time - ``available()`` reports
whether this environment can actually use it, and the import only happens
when a capture is started.
"""

from __future__ import annotations

import threading
from typing import Callable, Iterator, Optional

from backend.utils.logger import get_logger

logger = get_logger(__name__)

RawPacketCallback = Callable[[object], None]


class TSharkCaptureManager:
    """Capture manager that wraps pyshark.LiveCapture (tshark)."""

    def __init__(self, interface: Optional[str] = None, bpf_filter: str = ""):
        self.interface = interface
        self.bpf_filter = bpf_filter
        self._capture = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self.packet_count = 0

    @staticmethod
    def available() -> bool:
        """True if pyshark is importable AND the tshark binary is on PATH."""
        try:
            import shutil

            import pyshark  # noqa: F401
        except ImportError:
            return False
        return shutil.which("tshark") is not None

    def live_capture(self, interface: Optional[str] = None, bpf_filter: Optional[str] = None) -> Iterator[object]:
        """
        Generator that yields raw pyshark packets as tshark captures them.

        Usage:
            for packet in TSharkCaptureManager(iface).live_capture():
                print(packet)

        Raises RuntimeError if pyshark/tshark are unavailable.
        """
        import pyshark

        iface = interface if interface is not None else self.interface
        if not self.available():
            raise RuntimeError(
                "TSharkCaptureManager requires the 'pyshark' package and the 'tshark' "
                "binary on PATH. Install both, or use the Scapy backend instead."
            )

        capture = pyshark.LiveCapture(interface=iface, bpf_filter=bpf_filter or self.bpf_filter)
        yield from capture.sniff_continuously()

    # ------------------------------------------------------------------
    # CaptureBackend-compatible start/stop (see interface.py's protocol)
    # ------------------------------------------------------------------

    def start(self, on_packet: RawPacketCallback) -> None:
        """Begin capturing on a background daemon thread, invoking `on_packet` per packet."""
        if self._running:
            return
        try:
            import pyshark  # noqa: F401
        except ImportError as exc:
            raise RuntimeError(
                "TSharkCaptureManager requires the 'pyshark' package and the 'tshark' "
                "binary on PATH. Install both, or use the Scapy backend instead."
            ) from exc

        self._capture = pyshark.LiveCapture(interface=self.interface, bpf_filter=self.bpf_filter)
        self._running = True
        self.packet_count = 0

        def _run() -> None:
            try:
                for packet in self._capture.sniff_continuously():
                    self.packet_count += 1
                    on_packet(packet)
            except Exception:  # noqa: BLE001 - capture thread must not die silently
                logger.exception("TShark capture thread stopped unexpectedly")
            finally:
                self._running = False

        self._thread = threading.Thread(target=_run, name="tshark-capture", daemon=True)
        self._thread.start()
        logger.info("TShark capture started (interface=%s, filter='%s')", self.interface, self.bpf_filter)

    def stop(self) -> None:
        """Stop capturing. Idempotent - safe to call even if already stopped."""
        if self._capture is not None:
            try:
                self._capture.close()
            except Exception:  # noqa: BLE001 - closing is best-effort
                logger.warning("Failed to cleanly close TShark capture", exc_info=True)
            self._capture = None
        self._running = False
        logger.info("TShark capture stopped (packets=%d)", self.packet_count)

    @property
    def is_running(self) -> bool:
        return self._running


# Compatibility alias: capture.py historically exposed the PyShark backend
# under this name; keep both spellings working.
PySharkCaptureBackend = TSharkCaptureManager
