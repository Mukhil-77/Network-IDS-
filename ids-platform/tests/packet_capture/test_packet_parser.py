"""Tests for packet_parser.py, built entirely from synthetic in-memory scapy packets (no live capture)."""

from scapy.layers.inet import IP, TCP, UDP
from scapy.packet import Raw

from backend.packet_capture.packet_parser import parse_packet


def test_parses_tcp_packet_fields():
    pkt = IP(src="10.0.0.1", dst="10.0.0.2") / TCP(sport=51000, dport=80, flags="S") / Raw(load=b"hello")
    parsed = parse_packet(pkt)

    assert parsed is not None
    assert parsed.src_ip == "10.0.0.1"
    assert parsed.dst_ip == "10.0.0.2"
    assert parsed.src_port == 51000
    assert parsed.dst_port == 80
    assert parsed.protocol == "TCP"
    assert "SYN" in parsed.tcp_flags
    assert parsed.payload_length == 5


def test_parses_udp_packet_with_no_flags():
    pkt = IP(src="10.0.0.5", dst="10.0.0.6") / UDP(sport=5000, dport=53)
    parsed = parse_packet(pkt)

    assert parsed is not None
    assert parsed.protocol == "UDP"
    assert parsed.tcp_flags == frozenset()


def test_parses_syn_ack_flags_combined():
    pkt = IP(src="1.1.1.1", dst="2.2.2.2") / TCP(sport=443, dport=51000, flags="SA")
    parsed = parse_packet(pkt)
    assert parsed.tcp_flags == frozenset({"SYN", "ACK"})


def test_non_ip_packet_returns_none():
    from scapy.layers.l2 import ARP, Ether

    pkt = Ether() / ARP()
    assert parse_packet(pkt) is None


def test_icmp_packet_returns_none():
    from scapy.layers.inet import ICMP

    pkt = IP(src="10.0.0.1", dst="10.0.0.2") / ICMP()
    assert parse_packet(pkt) is None


def test_malformed_packet_does_not_raise():
    # An object that isn't even a scapy Packet - parse_packet must degrade gracefully, never raise.
    assert parse_packet(object()) is None
