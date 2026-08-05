"""Tests for flow_features.extract_flow_features()."""

import pytest

from backend.packet_capture.flow_features import extract_flow_features
from backend.packet_capture.flow_manager import Flow
from backend.packet_capture.packet_parser import ParsedPacket


def make_flow(fwd_lengths, bwd_lengths, start_time=1000.0, duration=2.0, flags=None):
    flow = Flow(
        flow_id="test-flow", key=("10.0.0.1", 5000, "10.0.0.2", 80, "TCP"),
        protocol="TCP", src_ip="10.0.0.1", dst_ip="10.0.0.2", src_port=5000, dst_port=80,
        start_time=start_time, last_seen=start_time,
    )
    n_fwd, n_bwd = len(fwd_lengths), len(bwd_lengths)
    total = max(n_fwd + n_bwd, 1)
    for i, length in enumerate(fwd_lengths):
        ts = start_time + (duration * i / total)
        flow.add_packet(ParsedPacket(
            timestamp=ts, src_ip="10.0.0.1", dst_ip="10.0.0.2", src_port=5000, dst_port=80,
            protocol="TCP", length=length, header_length=40, payload_length=max(length - 40, 0),
            tcp_flags=(flags or frozenset()) if i == 0 else frozenset(),
        ))
    for i, length in enumerate(bwd_lengths):
        ts = start_time + (duration * (n_fwd + i) / total)
        flow.add_packet(ParsedPacket(
            timestamp=ts, src_ip="10.0.0.2", dst_ip="10.0.0.1", src_port=80, dst_port=5000,
            protocol="TCP", length=length, header_length=40, payload_length=max(length - 40, 0),
            tcp_flags=frozenset(),
        ))
    flow.last_seen = start_time + duration
    return flow


def test_basic_counts_and_totals():
    flow = make_flow(fwd_lengths=[100, 200, 150], bwd_lengths=[300, 400])
    features = extract_flow_features(flow)

    assert features["Total Fwd Packets"] == 3
    assert features["Total Backward Packets"] == 2
    assert features["Total Length of Fwd Packets"] == 450
    assert features["Total Length of Bwd Packets"] == 700


def test_flow_duration_is_in_microseconds():
    flow = make_flow(fwd_lengths=[100], bwd_lengths=[100], duration=2.0)
    features = extract_flow_features(flow)
    assert features["Flow Duration"] == pytest.approx(2_000_000, rel=0.01)


def test_packet_length_stats():
    flow = make_flow(fwd_lengths=[100, 200], bwd_lengths=[300])
    features = extract_flow_features(flow)

    assert features["Min Packet Length"] == 100
    assert features["Max Packet Length"] == 300
    assert features["Packet Length Mean"] == pytest.approx(200.0)


def test_flag_counts():
    flow = make_flow(fwd_lengths=[100], bwd_lengths=[], flags=frozenset({"SYN", "ACK"}))
    features = extract_flow_features(flow)
    assert features["SYN Flag Count"] == 1
    assert features["ACK Flag Count"] == 1
    assert features["FIN Flag Count"] == 0


def test_empty_direction_does_not_crash_and_returns_zero():
    flow = make_flow(fwd_lengths=[100, 200], bwd_lengths=[])  # no backward traffic at all
    features = extract_flow_features(flow)

    assert features["Total Backward Packets"] == 0
    assert features["Bwd Packet Length Mean"] == 0.0
    assert features["Down/Up Ratio"] == 0.0


def test_flow_bytes_and_packets_per_second_are_nonzero_for_nonzero_duration():
    flow = make_flow(fwd_lengths=[100, 100], bwd_lengths=[100], duration=1.0)
    features = extract_flow_features(flow)
    assert features["Flow Bytes/s"] > 0
    assert features["Flow Packets/s"] > 0


def test_zero_duration_flow_does_not_divide_by_zero():
    flow = make_flow(fwd_lengths=[100], bwd_lengths=[], duration=0.0)
    features = extract_flow_features(flow)
    assert features["Flow Bytes/s"] == 0.0
    assert features["Flow Packets/s"] == 0.0


def test_returns_only_reconstructable_features_not_active_idle_or_subflow():
    flow = make_flow(fwd_lengths=[100], bwd_lengths=[100])
    features = extract_flow_features(flow)

    for unsupported in ("Active Mean", "Idle Mean", "Init_Win_bytes_forward", "Subflow Fwd Packets"):
        assert unsupported not in features
