"""
Flow -> NF-UQ-NIDS-v2 NetFlow features (Enhanced).

This module computes NetFlow/IPFIX-style features from live packet captures
matching the 43 original NF-UQ-NIDS-v2 features PLUS 15 enhanced statistical
features for better attack detection.

Enhanced features added:
- Flow asymmetry ratios (FWD_TO_BWD_PKT_RATIO, FWD_TO_BWD_BYTE_RATIO)
- Inter-arrival time statistics (AVG_IAT, STD_IAT, IAT_CV, MIN_IAT, MAX_IAT)
- Packet size entropy (PKT_SIZE_ENTROPY) - detects tunneling/exfiltration
- TCP flag ratios (SYN_TO_ACK_RATIO, RST_RATE, FIN_RATE)
- Packet size statistics (PKT_SIZE_MEAN, PKT_SIZE_STD, PKT_SIZE_SKEW)
- Throughput asymmetry (THROUGHPUT_RATIO)
- Port-based features (DST_PORT_ENTROPY approximation via port categories)
"""

from __future__ import annotations

import math
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


def _entropy(values):
    """Compute Shannon entropy of a list of values."""
    if not values:
        return 0.0
    from collections import Counter
    counts = Counter(values)
    total = len(values)
    ent = 0.0
    for count in counts.values():
        p = count / total
        if p > 0:
            ent -= p * math.log2(p)
    return ent


def _skewness(values):
    """Compute sample skewness."""
    if len(values) < 3:
        return 0.0
    n = len(values)
    mean = sum(values) / n
    m2 = sum((x - mean) ** 2 for x in values) / n
    m3 = sum((x - mean) ** 3 for x in values) / n
    if m2 == 0:
        return 0.0
    return (m3 / (m2 ** 1.5)) * (n / ((n - 1) * (n - 2))) ** 0.5


def _compute_iats(timestamps):
    """Compute inter-arrival times from sorted timestamps."""
    if len(timestamps) < 2:
        return []
    sorted_ts = sorted(timestamps)
    return [sorted_ts[i+1] - sorted_ts[i] for i in range(len(sorted_ts) - 1)]


def extract_nf_flow_features(flow: Flow) -> dict[str, float]:
    """
    Compute NF-UQ-NIDS-v2 NetFlow features + enhanced features for one completed flow.
    
    Returns a flat dict of feature name -> float.
    """
    # Duration in seconds
    duration_seconds = max(0.0, flow.last_seen - flow.start_time)
    duration_ms = duration_seconds * 1000
    duration_us = duration_seconds * 1_000_000
    
    # Forward/backward packet lengths
    fwd_lengths = flow.fwd_lengths
    bwd_lengths = flow.bwd_lengths
    all_lengths = fwd_lengths + bwd_lengths
    
    # All timestamps for IAT computation
    fwd_timestamps = getattr(flow, 'fwd_timestamps', [])
    bwd_timestamps = getattr(flow, 'bwd_timestamps', [])
    all_timestamps = fwd_timestamps + bwd_timestamps
    
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
    mean_pkt_len = (total_bytes / total_pkts) if total_pkts > 0 else 0
    std_pkt_len = math.sqrt(sum((l - mean_pkt_len) ** 2 for l in all_lengths) / total_pkts) if total_pkts > 1 else 0
    skew_pkt_len = _skewness(all_lengths)
    
    # TTL values (from first packet - we'd need to store this in Flow)
    min_ttl = 64
    max_ttl = 64
    
    # TCP flags
    tcp_flags = 0
    client_tcp_flags = 0
    server_tcp_flags = 0
    
    # Count TCP flags from flow
    syn_count = flow.flag_counts.get("SYN", 0)
    ack_count = flow.flag_counts.get("ACK", 0)
    fin_count = flow.flag_counts.get("FIN", 0)
    rst_count = flow.flag_counts.get("RST", 0)
    psh_count = flow.flag_counts.get("PSH", 0)
    urg_count = flow.flag_counts.get("URG", 0)
    ece_count = flow.flag_counts.get("ECE", 0)
    cwr_count = flow.flag_counts.get("CWR", 0)
    
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
    duration_in_ms = duration_ms
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
    
    # Retransmission features
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
    
    # ============ ENHANCED FEATURES ============
    
    # Flow asymmetry ratios
    fwd_to_bwd_pkt_ratio = fwd_pkts / max(bwd_pkts, 1)
    fwd_to_bwd_byte_ratio = fwd_bytes / max(bwd_bytes, 1)
    throughput_ratio = src_to_dst_avg_throughput / max(dst_to_src_avg_throughput, 1)
    
    # Inter-arrival time statistics
    all_iats = _compute_iats(all_timestamps)
    fwd_iats = _compute_iats(fwd_timestamps)
    bwd_iats = _compute_iats(bwd_timestamps)
    
    avg_iat = sum(all_iats) / len(all_iats) if all_iats else 0
    std_iat = math.sqrt(sum((x - avg_iat) ** 2 for x in all_iats) / len(all_iats)) if len(all_iats) > 1 else 0
    cv_iat = std_iat / max(avg_iat, 1e-6) if all_iats else 0
    min_iat = min(all_iats) if all_iats else 0
    max_iat = max(all_iats) if all_iats else 0
    
    # Forward/backward IAT stats
    avg_fwd_iat = sum(fwd_iats) / len(fwd_iats) if fwd_iats else 0
    avg_bwd_iat = sum(bwd_iats) / len(bwd_iats) if bwd_iats else 0
    
    # Packet size entropy (detects tunneling, exfiltration, encrypted traffic)
    pkt_size_entropy = _entropy(all_lengths)
    
    # TCP flag ratios (attack indicators)
    syn_to_ack_ratio = syn_count / max(ack_count, 1)
    rst_rate = rst_count / max(total_pkts, 1)
    fin_rate = fin_count / max(total_pkts, 1)
    psh_rate = psh_count / max(total_pkts, 1)
    
    # Port category entropy approximation (well-known vs ephemeral)
    dst_port = flow.dst_port
    src_port = flow.src_port
    # Well-known ports (0-1023) vs registered (1024-49151) vs ephemeral (49152-65535)
    def port_category(p):
        if p <= 1023: return 0  # well-known
        elif p <= 49151: return 1  # registered
        else: return 2  # ephemeral
    port_cats = [port_category(dst_port), port_category(src_port)]
    port_entropy = _entropy(port_cats)
    
    features = {
        # === Original 43 NF-UQ-NIDS-v2 features ===
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
        
        # === Enhanced features (15 new) ===
        # Flow asymmetry
        'FWD_TO_BWD_PKT_RATIO': float(fwd_to_bwd_pkt_ratio),
        'FWD_TO_BWD_BYTE_RATIO': float(fwd_to_bwd_byte_ratio),
        'THROUGHPUT_RATIO': float(throughput_ratio),
        
        # Inter-arrival time statistics
        'AVG_IAT': float(avg_iat * 1_000_000),  # microseconds
        'STD_IAT': float(std_iat * 1_000_000),
        'CV_IAT': float(cv_iat),
        'MIN_IAT': float(min_iat * 1_000_000),
        'MAX_IAT': float(max_iat * 1_000_000),
        'AVG_FWD_IAT': float(avg_fwd_iat * 1_000_000),
        'AVG_BWD_IAT': float(avg_bwd_iat * 1_000_000),
        
        # Packet size statistics
        'PKT_SIZE_MEAN': float(mean_pkt_len),
        'PKT_SIZE_STD': float(std_pkt_len),
        'PKT_SIZE_SKEW': float(skew_pkt_len),
        'PKT_SIZE_ENTROPY': float(pkt_size_entropy),
        
        # TCP flag ratios
        'SYN_TO_ACK_RATIO': float(syn_to_ack_ratio),
        'RST_RATE': float(rst_rate),
        'FIN_RATE': float(fin_rate),
        'PSH_RATE': float(psh_rate),
        
        # Port entropy
        'PORT_ENTROPY': float(port_entropy),
    }
    
    return features


# Keep the old function name for backward compatibility
def extract_flow_features(flow: Flow) -> dict[str, float]:
    """Extract features from flow - now uses NF-UQ-NIDS-v2 features + enhanced."""
    return extract_nf_flow_features(flow)


# List of enhanced feature names for reference
ENHANCED_FEATURE_NAMES = [
    'FWD_TO_BWD_PKT_RATIO',
    'FWD_TO_BWD_BYTE_RATIO', 
    'THROUGHPUT_RATIO',
    'AVG_IAT',
    'STD_IAT',
    'CV_IAT',
    'MIN_IAT',
    'MAX_IAT',
    'AVG_FWD_IAT',
    'AVG_BWD_IAT',
    'PKT_SIZE_MEAN',
    'PKT_SIZE_STD',
    'PKT_SIZE_SKEW',
    'PKT_SIZE_ENTROPY',
    'SYN_TO_ACK_RATIO',
    'RST_RATE',
    'FIN_RATE',
    'PSH_RATE',
    'PORT_ENTROPY',
]

# Combined feature list (original 43 + 19 enhanced = 62 total)
ALL_FEATURE_NAMES = [
    'IPV4_SRC_ADDR', 'L4_SRC_PORT', 'IPV4_DST_ADDR', 'L4_DST_PORT', 'PROTOCOL', 'L7_PROTO',
    'IN_BYTES', 'IN_PKTS', 'OUT_BYTES', 'OUT_PKTS', 'TCP_FLAGS', 'CLIENT_TCP_FLAGS', 'SERVER_TCP_FLAGS',
    'FLOW_DURATION_MILLISECONDS', 'DURATION_IN', 'DURATION_OUT', 'MIN_TTL', 'MAX_TTL',
    'LONGEST_FLOW_PKT', 'SHORTEST_FLOW_PKT', 'MIN_IP_PKT_LEN', 'MAX_IP_PKT_LEN',
    'SRC_TO_DST_SECOND_BYTES', 'DST_TO_SRC_SECOND_BYTES',
    'RETRANSMITTED_IN_BYTES', 'RETRANSMITTED_IN_PKTS', 'RETRANSMITTED_OUT_BYTES', 'RETRANSMITTED_OUT_PKTS',
    'SRC_TO_DST_AVG_THROUGHPUT', 'DST_TO_SRC_AVG_THROUGHPUT',
    'NUM_PKTS_UP_TO_128_BYTES', 'NUM_PKTS_128_TO_256_BYTES', 'NUM_PKTS_256_TO_512_BYTES',
    'NUM_PKTS_512_TO_1024_BYTES', 'NUM_PKTS_1024_TO_1514_BYTES',
    'TCP_WIN_MAX_IN', 'TCP_WIN_MAX_OUT', 'ICMP_TYPE', 'ICMP_IPV4_TYPE',
    'DNS_QUERY_ID', 'DNS_QUERY_TYPE', 'DNS_TTL_ANSWER', 'FTP_COMMAND_RET_CODE',
] + ENHANCED_FEATURE_NAMES