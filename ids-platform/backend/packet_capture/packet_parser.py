"""
Raw packet -> ParsedPacket.

Both capture backends (Scapy, PyShark - see capture.py) ultimately hand a
packet to this module. `parse_packet()` is the one place that understands
packet layers; everything downstream (flow_manager.py, flow_features.py)
only ever sees the plain ParsedPacket dataclass, so it's testable with
synthetic packets and doesn't care how the packet was captured.

Only IPv4/IPv6 TCP/UDP/ICMP packets are supported - the transport
protocols CIC-IDS2017 covers (IPv4 TCP/UDP) plus the IPv6 equivalents and
ICMP, since IPv6-only networks and ping traffic are common and would
otherwise starve the live packet feed. Anything else (ARP, ...) is
filtered out here and returned as None; capture.py skips it rather than
passing it to the flow manager.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

from scapy.layers.inet import ICMP, IP, TCP, UDP
from scapy.layers.inet6 import IPv6
from scapy.packet import Packet

from backend.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class ParsedPacket:
    """One IPv4/IPv6 TCP/UDP/ICMP packet, reduced to the fields flow reconstruction needs."""

    timestamp: float  # seconds, epoch (matches scapy's packet.time when available)
    src_ip: str
    dst_ip: str
    src_port: int
    dst_port: int
    protocol: str  # "TCP", "UDP" or "ICMP"
    length: int  # total IP packet length in bytes (header + payload)
    header_length: int  # combined IP + transport header length, used by *_Header_Length features
    payload_length: int  # transport-layer payload size
    tcp_flags: frozenset[str]  # subset of {"SYN","ACK","FIN","RST","PSH","URG","ECE","CWR"}; empty for UDP/ICMP


_TCP_FLAG_BITS = {
    "F": "FIN", "S": "SYN", "R": "RST", "P": "PSH",
    "A": "ACK", "U": "URG", "E": "ECE", "C": "CWR",
}


def _extract_tcp_flags(tcp_layer: TCP) -> frozenset[str]:
    flags_str = str(tcp_layer.flags)  # scapy renders flags as e.g. "SA" for SYN+ACK
    return frozenset(_TCP_FLAG_BITS[c] for c in flags_str if c in _TCP_FLAG_BITS)


def parse_packet(raw_packet: Packet) -> Optional[ParsedPacket]:
    """
    Parse one scapy Packet into a ParsedPacket, or return None if it isn't
    an IPv4/IPv6 TCP/UDP/ICMP packet (the kinds CIC-IDS2017 flows represent).

    Never raises - a packet that fails to parse (malformed, truncated,
    unsupported layer combination) is logged at debug level and skipped,
    since one bad packet must never take down the capture loop.
    """
    try:
        if IP not in raw_packet and IPv6 not in raw_packet:
            return None

        ip_layer = raw_packet[IP] if IP in raw_packet else raw_packet[IPv6]
        timestamp = float(getattr(raw_packet, "time", time.time()))

        if TCP in raw_packet:
            transport = raw_packet[TCP]
            protocol = "TCP"
            tcp_flags = _extract_tcp_flags(transport)
            header_length = len(ip_layer) - len(transport.payload) if transport.payload else len(ip_layer)
            src_port, dst_port = int(transport.sport), int(transport.dport)
        elif UDP in raw_packet:
            transport = raw_packet[UDP]
            protocol = "UDP"
            tcp_flags = frozenset()
            header_length = len(ip_layer) - len(transport.payload) if transport.payload else len(ip_layer)
            src_port, dst_port = int(transport.sport), int(transport.dport)
        elif ICMP in raw_packet:
            transport = raw_packet[ICMP]
            protocol = "ICMP"
            tcp_flags = frozenset()
            header_length = len(ip_layer) - len(transport.payload) if transport.payload else len(ip_layer)
            src_port, dst_port = 0, 0
        else:
            return None  # not TCP/UDP/ICMP (e.g. ARP) - out of scope, matches CIC-IDS2017's coverage

        payload_length = len(transport.payload) if transport.payload else 0

        return ParsedPacket(
            timestamp=timestamp,
            src_ip=str(ip_layer.src),
            dst_ip=str(ip_layer.dst),
            src_port=src_port,
            dst_port=dst_port,
            protocol=protocol,
            length=int(len(ip_layer)),
            header_length=int(header_length),
            payload_length=int(payload_length),
            tcp_flags=tcp_flags,
        )
    except Exception:  # noqa: BLE001 - one malformed packet must never crash the capture loop
        logger.debug("Failed to parse packet; skipping", exc_info=True)
        return None
