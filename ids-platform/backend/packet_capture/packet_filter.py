"""
Berkeley Packet Filter (BPF) string construction.

Applied at the capture layer (both Scapy's sniff() and PyShark's
LiveCapture accept a BPF string), so uninteresting traffic is dropped by
the OS/kernel packet filter before it ever reaches Python - much cheaper
than filtering in packet_parser.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PacketFilterConfig:
    """
    Declarative capture filter. Defaults to "IPv4/IPv6 TCP or UDP only" -
    the transport protocols CIC-IDS2017 (and therefore the trained model)
    cover, on both IP versions so IPv6-heavy environments still feed the
    live packet view; see packet_parser.py's module docstring.
    """

    protocols: tuple[str, ...] = ("tcp", "udp")
    exclude_hosts: list[str] = field(default_factory=list)  # e.g. exclude the capture host's own management IP
    ports: Optional[list[int]] = None  # None = all ports


def build_bpf_filter(config: Optional[PacketFilterConfig] = None) -> str:
    """
    Build a BPF filter string from a PacketFilterConfig.

    Example:
        build_bpf_filter(PacketFilterConfig(protocols=("tcp",), exclude_hosts=["10.0.0.1"]))
        -> "(ip or ip6) and tcp and not host 10.0.0.1"
    """
    cfg = config or PacketFilterConfig()

    clauses = ["(ip or ip6)"]

    if cfg.protocols:
        clauses.append("(" + " or ".join(cfg.protocols) + ")")

    if cfg.ports:
        port_clause = " or ".join(f"port {p}" for p in cfg.ports)
        clauses.append(f"({port_clause})")

    for host in cfg.exclude_hosts:
        clauses.append(f"not host {host}")

    return " and ".join(clauses)
