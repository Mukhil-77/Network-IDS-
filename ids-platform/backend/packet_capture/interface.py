"""
Interface discovery + the CaptureBackend contract.

`CaptureBackend` is the seam that lets capture.py support Scapy and
PyShark interchangeably - both wrap a different underlying library but
expose the same start()/stop() shape, so PacketCapture (capture.py's
orchestrator) never needs to know which one it's driving.
"""

from __future__ import annotations

import re
import sys
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


_GUID_RE = re.compile(r"\{([0-9A-Fa-f-]{36})\}")


def _extract_guid(name: str) -> str | None:
    """Pull the GUID out of e.g. ``\\Device\\NPF_{18EB3A7D-...}\"``, or None."""
    match = _GUID_RE.search(name)
    return match.group(1) if match else None


def _friendly_from_registry(guid: str) -> str:
    """Map an NPF GUID to the Windows-friendly adapter name, or '' if unknown."""
    if sys.platform != "win32":
        return ""
    try:
        import winreg

        base = r"SYSTEM\CurrentControlSet\Control\Network\{4D36E972-E325-11CE-BFC1-08002BE10318}"
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, f"{base}\\{{{guid}}}\\Connection")
        try:
            value, _type = winreg.QueryValueEx(key, "Name")
            return str(value)
        finally:
            winreg.CloseKey(key)
    except OSError:
        return ""


def friendly_name(raw: str) -> str:
    """
    Human-readable label for a raw interface name.

    Turns Windows Npcap handles (``\\Device\\NPF_{GUID}``) into the adapter's
    friendly description (e.g. "Intel(R) Wi-Fi 6 AX201 (NPF_{...})") so the UI
    isn't a wall of opaque GUIDs, falling back to a readable placeholder when
    the friendly name can't be looked up. Non-Windows names are kept as-is.
    """
    guid = _extract_guid(raw)
    if guid:
        readable = _friendly_from_registry(guid)
        if readable:
            return f"{readable} · NPF_{guid}"
        return f"Network adapter · NPF_{guid}"
    return raw


def network_interfaces() -> list[dict]:
    """
    Enumerate interfaces as {name, description} dicts for the API.

    `name` is the raw handle scapy needs to bind to a device; `description`
    is the friendly label shown in the UI. Defaults to [] on error.
    """
    try:
        return [
            {"name": name, "description": friendly_name(name)}
            for name in list_interfaces()
        ]
    except Exception:  # noqa: BLE001
        logger.warning("Could not enumerate network interface details", exc_info=True)
        return []


def default_interface() -> str | None:
    """Best-effort guess at the primary interface, or None if it can't be determined."""
    try:
        from scapy.all import conf
        return str(conf.iface) if conf.iface else None
    except Exception:  # noqa: BLE001
        return None
