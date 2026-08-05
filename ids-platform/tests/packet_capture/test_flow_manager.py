"""Flow reconstruction tests - synthetic ParsedPacket objects, no live capture or scapy needed here."""

import threading
import time

import pytest

from backend.packet_capture.flow_manager import Flow, FlowManager
from backend.packet_capture.packet_parser import ParsedPacket


def make_packet(src_ip, src_port, dst_ip, dst_port, protocol="TCP", length=100, ts=None, flags=frozenset()):
    return ParsedPacket(
        timestamp=ts if ts is not None else time.time(),
        src_ip=src_ip, dst_ip=dst_ip, src_port=src_port, dst_port=dst_port,
        protocol=protocol, length=length, header_length=40, payload_length=length - 40,
        tcp_flags=flags,
    )


def test_first_packet_creates_new_flow():
    fm = FlowManager()
    pkt = make_packet("10.0.0.1", 5000, "10.0.0.2", 80)
    flow = fm.add_packet(pkt)

    assert isinstance(flow, Flow)
    assert flow.src_ip == "10.0.0.1"
    assert flow.dst_ip == "10.0.0.2"
    assert flow.packet_count == 1
    assert fm.active_flow_count() == 1


def test_packets_in_both_directions_join_same_flow():
    fm = FlowManager()
    fwd = make_packet("10.0.0.1", 5000, "10.0.0.2", 80)
    bwd = make_packet("10.0.0.2", 80, "10.0.0.1", 5000)  # reverse direction, same connection

    fm.add_packet(fwd)
    flow = fm.add_packet(bwd)

    assert fm.active_flow_count() == 1
    assert len(flow.fwd_lengths) == 1
    assert len(flow.bwd_lengths) == 1


def test_different_ports_create_different_flows():
    fm = FlowManager()
    fm.add_packet(make_packet("10.0.0.1", 5000, "10.0.0.2", 80))
    fm.add_packet(make_packet("10.0.0.1", 5001, "10.0.0.2", 80))
    assert fm.active_flow_count() == 2


def test_fin_flag_closes_flow_immediately():
    closed_flows = []
    fm = FlowManager(on_flow_closed=closed_flows.append)

    fm.add_packet(make_packet("10.0.0.1", 5000, "10.0.0.2", 80, flags=frozenset({"SYN"})))
    fm.add_packet(make_packet("10.0.0.1", 5000, "10.0.0.2", 80, flags=frozenset({"FIN"})))

    assert fm.active_flow_count() == 0
    assert len(closed_flows) == 1
    assert closed_flows[0].flag_counts["FIN"] == 1


def test_rst_flag_closes_flow_immediately():
    closed_flows = []
    fm = FlowManager(on_flow_closed=closed_flows.append)
    fm.add_packet(make_packet("10.0.0.1", 5000, "10.0.0.2", 80, flags=frozenset({"RST"})))
    assert fm.active_flow_count() == 0
    assert len(closed_flows) == 1


def test_idle_timeout_closes_flow_via_background_thread():
    closed_flows = []
    fm = FlowManager(on_flow_closed=closed_flows.append, idle_timeout_seconds=0.2, check_interval_seconds=0.1)
    fm.start()
    try:
        old_ts = time.time() - 10  # already "idle" the moment it's added
        fm.add_packet(make_packet("10.0.0.1", 5000, "10.0.0.2", 80, ts=old_ts))
        assert fm.active_flow_count() == 1

        time.sleep(0.5)
        assert fm.active_flow_count() == 0
        assert len(closed_flows) == 1
    finally:
        fm.stop()


def test_close_all_flushes_remaining_flows():
    closed_flows = []
    fm = FlowManager(on_flow_closed=closed_flows.append)
    fm.add_packet(make_packet("10.0.0.1", 5000, "10.0.0.2", 80))
    fm.add_packet(make_packet("10.0.0.3", 6000, "10.0.0.4", 443))

    fm.close_all()

    assert fm.active_flow_count() == 0
    assert len(closed_flows) == 2


def test_concurrent_packet_additions_are_thread_safe():
    fm = FlowManager()

    def worker(port_offset):
        for i in range(50):
            fm.add_packet(make_packet("10.0.0.1", 5000 + port_offset, "10.0.0.2", 80))

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert fm.active_flow_count() == 10  # 10 distinct source ports -> 10 distinct flows
    total_packets = sum(f.packet_count for f in fm._flows.values())  # noqa: SLF001 - test-only introspection
    assert total_packets == 500


def test_on_flow_closed_exception_does_not_propagate():
    def bad_callback(flow):
        raise RuntimeError("subscriber bug")

    fm = FlowManager(on_flow_closed=bad_callback)
    # Must not raise, even though the callback does.
    fm.add_packet(make_packet("10.0.0.1", 5000, "10.0.0.2", 80, flags=frozenset({"RST"})))
