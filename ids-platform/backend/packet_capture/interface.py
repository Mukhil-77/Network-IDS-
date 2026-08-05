"""
Interface discovery + the CaptureBackend contract.

`CaptureBackend` is the seam that lets capture.py support Scapy and
PyShark interchangeably - both wrap a different underlying library but
expose the same start()/stop() shape, so PacketCapture (capture.py's
orchestrator) never needs to know which one it's driving.
"""

from __future__ import annotations

from typing import Callable, Protocol

from backend.utils.logger import get_logger

logger = get_logger(__name__)

# What a capture backend hands back per packet - kept as `object` here
# (rather than importing scapy's Packet type) so this module has no hard
# dependency on scapy; packet_parser.py is where the real typing lives.
RawPacketCallback = Callable[[object], None]


class CaptureBackend(Protocol):
    """Implemented by ScapyCaptureBackend and PySharkCaptureBackend (see capture.py)."""

    def start(self, on_packet: RawPacketCallback) -> None:
        """Begin capturing on a background thread, invoking `on_packet` for each captured packet."""
        ...

    def stop(self) -> None:
        """Stop capturing. Idempotent - safe to call even if already stopped."""
        ...


def list_interfaces() -> list[str]:
    """
    Return the names of available network interfaces.

    Returns an empty list (rather than raising) if scapy isn't installed or
    interface enumeration isn't possible in the current environment (e.g.
    no packet-capture permissions, sandboxed/containerized runtime) - this
    lets callers (a future /packet-capture/interfaces API endpoint, or a
    CLI) degrade gracefully instead of crashing on import.
    """
    try:
        from scapy.all import get_if_list
        return list(get_if_list())
    except Exception:  # noqa: BLE001 - environment-dependent; never fatal
        logger.warning("Could not enumerate network interfaces", exc_info=True)
        return []


def default_interface() -> str | None:
    """Best-effort guess at the primary interface, or None if it can't be determined."""
    try:
        from scapy.all import conf
        return str(conf.iface) if conf.iface else None
    except Exception:  # noqa: BLE001
        return None
