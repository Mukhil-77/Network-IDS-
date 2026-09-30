"""
Flow -> NF-UQ-NIDS-v2 NetFlow features.

This module computes NetFlow/IPFIX-style features from live packet captures
that match the 43 features the LightGBM model was trained on.

Features extracted (matching NF-UQ-NIDS-v2):
- IPV4_SRC_ADDR, L4_SRC_PORT, IPV4_DST_ADDR, L4_DST_PORT, PROTOCOL, L7_PROTO
- IN_BYTES, IN_PKTS, OUT_BYTES, OUT_PKTS
- TCP_FLAGS, CLIENT_TCP_FLAGS, SERVER_TCP_FLAGS
- FLOW_DURATION_MILLISECONDS, DURATION_IN, DURATION_OUT
- MIN_TTL, MAX_TTL, LONGEST_FLOW_PKT, SHORTEST_FLOW_PKT
- MIN_IP_PKT_LEN, MAX_IP_PKT_LEN
- SRC_TO_DST_SECOND_BYTES, DST_TO_SRC_SECOND_BYTES
- RETRANSMITTED_IN_BYTES, RETRANSMITTED_IN_PKTS
- RETRANSMITTED_OUT_BYTES, RETRANSMITTED_OUT_PKTS
- SRC_TO_DST_AVG_THROUGHPUT, DST_TO_SRC_AVG_THROUGHPUT
- NUM_PKTS_UP_TO_128_BYTES, NUM_PKTS_128_TO_256_BYTES
- NUM_PKTS_256_TO_512_BYTES, NUM_PKTS_512_TO_1024_BYTES
- NUM_PKTS_1024_TO_1514_BYTES
- TCP_WIN_MAX_IN, TCP_WIN_MAX_OUT
- ICMP_TYPE, ICMP_IPV4_TYPE
- DNS_QUERY_ID, DNS_QUERY_TYPE, DNS_TTL_ANSWER
- FTP_COMMAND_RET_CODE
"""

from __future__ import annotations

import time
from typing import Optional

from backend.packet_capture.flow_manager import Flow
from backend.utils.logger import get_logger

logger = get_logger(__name__)

# Conversion factor for IP to integer
def ip_to_int(ip: str) -> int:
    """Convert IPv4 address string to integer."""
    try:
        parts = ip.split('.')
        if len(parts) == 4:
            return (int(parts[0]) << 24) | (int(parts[1]) << 16) | (int(parts[2]) << 8) | int(parts[3])
    except Exception:
        pass
    return 0


def _safe_get(flow: Flow, attr: str, default: float = 0.0) -> float:
    """Safely get a float attribute from flow."""
    try:
        return float(getattr(flow, attr, default))
    except Exception:
        return default


def extract_nf_flow_features(flow: Flow) -> dict[str, float]:
    """
    Compute NF-UQ-NIDS-v2 NetFlow features for one completed flow.
    
    Returns a flat dict of feature name -> float matching the 43 features
    the LightGBM model expects.
    """
    # Duration in seconds
    duration_seconds = max(0.0, flow.last_seen - flow.start_time)
    duration_ms = duration_seconds * 1000
    duration_us = duration_seconds * 1_000_000
    
    # Forward/backward packet lengths
    fwd_lengths = flow.fwd_lengths
    bwd_lengths = flow.bwd_lengths
    all_lengths = fwd_lengths + bwd_lengths
    
    # Packet counts
    fwd_pkts = len(fwd_lengths)
    bwd_pkts = len(bwd_lengths)
    total_pkts = fwd_pkts + bwd_pkts
    
    # Byte counts
    fwd_bytes = sum(fwd_lengths)
    bwd_bytes = sum(bwd_lengths)
    total_bytes = fwd_bytes + bwd_bytes
    
    # Packet size stats
    min_pkt_len = min(all_lengths) if all_lengths else 0
    max_pkt_len = max(all_lengths) if all_lengths else 0
    
    # TTL values (from first packet - we'd need to store this in Flow)
    # For now, use defaults as we don't capture TTL in current Flow
    min_ttl = 64
    max_ttl = 64
    
    # TCP flags
    tcp_flags = 0
    client_tcp_flags = 0
    server_tcp_flags = 0
    
    # Count TCP flags from flow
    for flag, count in flow.flag_counts.items():
        if count > 0:
            if flag == "FIN":
                tcp_flags |= 0x01
            elif flag == "SYN":
                tcp_flags |= 0x02
            elif flag == "RST":
                tcp_flags |= 0x04
            elif flag == "PSH":
                tcp_flags |= 0x08
            elif flag == "ACK":
                tcp_flags |= 0x10
            elif flag == "URG":
                tcp_flags |= 0x20
            elif flag == "ECE":
                tcp_flags |= 0x40
            elif flag == "CWR":
                tcp_flags |= 0x80
    
    # Client/server TCP flags (forward/backward)
    if flow.fwd_psh > 0:
        client_tcp_flags |= 0x08
    if flow.fwd_urg > 0:
        client_tcp_flags |= 0x20
    if flow.bwd_psh > 0:
        server_tcp_flags |= 0x08
    if flow.bwd_urg > 0:
        server_tcp_flags |= 0x20
    
    # Flow duration fields (in milliseconds)
    flow_duration_ms = duration_ms
    duration_in_ms = duration_ms  # Same for now, could be refined
    duration_out_ms = duration_ms
    
    # Packet size distribution
    num_pkts_up_to_128 = sum(1 for l in all_lengths if l <= 128)
    num_pkts_128_to_256 = sum(1 for l in all_lengths if 128 < l <= 256)
    num_pkts_256_to_512 = sum(1 for l in all_lengths if 256 < l <= 512)
    num_pkts_512_to_1024 = sum(1 for l in all_lengths if 512 < l <= 1024)
    num_pkts_1024_to_1514 = sum(1 for l in all_lengths if 1024 < l <= 1514)
    
    # TCP window sizes (not captured in current Flow, use defaults)
    tcp_win_max_in = 0
    tcp_win_max_out = 0
    
    # ICMP/DNS/FTP features (not captured, use defaults)
    icmp_type = 0
    icmp_ipv4_type = 0
    dns_query_id = 0
    dns_query_type = 0
    dns_ttl_answer = 0
    ftp_command_ret_code = 0
    
    # Throughput
    src_to_dst_avg_throughput = (fwd_bytes / duration_seconds) if duration_seconds > 0 else 0
    dst_to_src_avg_throughput = (bwd_bytes / duration_seconds) if duration_seconds > 0 else 0
    
    # Retransmission features (not easily computable without deep packet inspection)
    retransmitted_in_bytes = 0
    retransmitted_in_pkts = 0
    retransmitted_out_bytes = 0
    retransmitted_out_pkts = 0
    
    # Second bytes (approximation)
    src_to_dst_second_bytes = fwd_bytes
    dst_to_src_second_bytes = bwd_bytes
    
    # L7 proto
    l7_proto = 0
    if flow.protocol == "TCP":
        l7_proto = 6
    elif flow.protocol == "UDP":
        l7_proto = 17
    elif flow.protocol == "ICMP":
        l7_proto = 1
    
    features = {
        'IPV4_SRC_ADDR': float(ip_to_int(flow.src_ip)),
        'L4_SRC_PORT': float(flow.src_port),
        'IPV4_DST_ADDR': float(ip_to_int(flow.dst_ip)),
        'L4_DST_PORT': float(flow.dst_port),
        'PROTOCOL': 6.0 if flow.protocol == "TCP" else (17.0 if flow.protocol == "UDP" else 1.0),
        'L7_PROTO': float(l7_proto),
        'IN_BYTES': float(fwd_bytes),
        'IN_PKTS': float(fwd_pkts),
        'OUT_BYTES': float(bwd_bytes),
        'OUT_PKTS': float(bwd_pkts),
        'TCP_FLAGS': float(tcp_flags),
        'CLIENT_TCP_FLAGS': float(client_tcp_flags),
        'SERVER_TCP_FLAGS': float(server_tcp_flags),
        'FLOW_DURATION_MILLISECONDS': float(flow_duration_ms),
        'DURATION_IN': float(duration_in_ms),
        'DURATION_OUT': float(duration_out_ms),
        'MIN_TTL': float(min_ttl),
        'MAX_TTL': float(max_ttl),
        'LONGEST_FLOW_PKT': float(max_pkt_len),
        'SHORTEST_FLOW_PKT': float(min_pkt_len),
        'MIN_IP_PKT_LEN': float(min_pkt_len),
        'MAX_IP_PKT_LEN': float(max_pkt_len),
        'SRC_TO_DST_SECOND_BYTES': float(src_to_dst_second_bytes),
        'DST_TO_SRC_SECOND_BYTES': float(dst_to_src_second_bytes),
        'RETRANSMITTED_IN_BYTES': float(retransmitted_in_bytes),
        'RETRANSMITTED_IN_PKTS': float(retransmitted_in_pkts),
        'RETRANSMITTED_OUT_BYTES': float(retransmitted_out_bytes),
        'RETRANSMITTED_OUT_PKTS': float(retransmitted_out_pkts),
        'SRC_TO_DST_AVG_THROUGHPUT': float(src_to_dst_avg_throughput),
        'DST_TO_SRC_AVG_THROUGHPUT': float(dst_to_src_avg_throughput),
        'NUM_PKTS_UP_TO_128_BYTES': float(num_pkts_up_to_128),
        'NUM_PKTS_128_TO_256_BYTES': float(num_pkts_128_to_256),
        'NUM_PKTS_256_TO_512_BYTES': float(num_pkts_256_to_512),
        'NUM_PKTS_512_TO_1024_BYTES': float(num_pkts_512_to_1024),
        'NUM_PKTS_1024_TO_1514_BYTES': float(num_pkts_1024_to_1514),
        'TCP_WIN_MAX_IN': float(tcp_win_max_in),
        'TCP_WIN_MAX_OUT': float(tcp_win_max_out),
        'ICMP_TYPE': float(icmp_type),
        'ICMP_IPV4_TYPE': float(icmp_ipv4_type),
        'DNS_QUERY_ID': float(dns_query_id),
        'DNS_QUERY_TYPE': float(dns_query_type),
        'DNS_TTL_ANSWER': float(dns_ttl_answer),
        'FTP_COMMAND_RET_CODE': float(ftp_command_ret_code),
    }
    
    return features


# Keep the old function name for backward compatibility
def extract_flow_features(flow: Flow) -> dict[str, float]:
    """Extract features from flow - now uses NF-UQ-NIDS-v2 features."""
    return extract_nf_flow_features(flow)