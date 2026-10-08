"""
Feature Schema for SOC Platform IDS (NF-UQ-NIDS-v2).

This module defines the canonical feature set used for both training and inference.
All feature engineering, model training, and inference must use this canonical schema.
"""

from __future__ import annotations

from typing import List, Dict, Set
from dataclasses import dataclass
from enum import Enum


class FeatureType(Enum):
    """Feature type classification for documentation and validation."""
    NUMERIC = "numeric"
    CATEGORICAL = "categorical"
    TEMPORAL = "temporal"
    IDENTIFIER = "identifier"


@dataclass(frozen=True)
class FeatureSpec:
    """Specification for a single feature."""
    name: str
    feature_type: FeatureType
    description: str = ""
    required: bool = True
    # For numeric features
    min_value: float = None
    max_value: float = None
    # For categorical features
    categories: list = None


# Canonical feature set - the 41 features the LightGBM model expects (NF-UQ-NIDS-v2)
# These match the features in models/v2/feature_names.json
CANONICAL_FEATURES: list[str] = [
    # Core flow identifiers
    "IPV4_SRC_ADDR",
    "L4_SRC_PORT",
    "IPV4_DST_ADDR",
    "L4_DST_PORT",
    "PROTOCOL",
    "L7_PROTO",
    
    # Byte/packet counts
    "IN_BYTES",
    "IN_PKTS",
    "OUT_BYTES",
    "OUT_PKTS",
    
    # TCP flags
    "TCP_FLAGS",
    "CLIENT_TCP_FLAGS",
    "SERVER_TCP_FLAGS",
    
    # Duration (milliseconds)
    "FLOW_DURATION_MILLISECONDS",
    "DURATION_IN",
    "DURATION_OUT",
    
    # TTL
    "MIN_TTL",
    "MAX_TTL",
    
    # Packet lengths
    "LONGEST_FLOW_PKT",
    "SHORTEST_FLOW_PKT",
    "MIN_IP_PKT_LEN",
    "MAX_IP_PKT_LEN",
    
    # Second bytes
    "SRC_TO_DST_SECOND_BYTES",
    "DST_TO_SRC_SECOND_BYTES",
    
    # Retransmissions
    "RETRANSMITTED_IN_BYTES",
    "RETRANSMITTED_IN_PKTS",
    "RETRANSMITTED_OUT_BYTES",
    "RETRANSMITTED_OUT_PKTS",
    
    # Throughput
    "SRC_TO_DST_AVG_THROUGHPUT",
    "DST_TO_SRC_AVG_THROUGHPUT",
    
    # Packet size distribution
    "NUM_PKTS_UP_TO_128_BYTES",
    "NUM_PKTS_128_TO_256_BYTES",
    "NUM_PKTS_256_TO_512_BYTES",
    "NUM_PKTS_512_TO_1024_BYTES",
    "NUM_PKTS_1024_TO_1514_BYTES",
    
    # TCP window
    "TCP_WIN_MAX_IN",
    "TCP_WIN_MAX_OUT",
    
    # ICMP/DNS/FTP
    "ICMP_TYPE",
    "ICMP_IPV4_TYPE",
    "DNS_QUERY_ID",
    "DNS_QUERY_TYPE",
    "DNS_TTL_ANSWER",
    "FTP_COMMAND_RET_CODE",
]

# Enhanced features (computed from live traffic but not in original training)
# These are extracted by flow_features.py but zero-filled for model compatibility
ENHANCED_FEATURES: list[str] = [
    # Flow asymmetry
    "FWD_TO_BWD_PKT_RATIO",
    "FWD_TO_BWD_BYTE_RATIO",
    "THROUGHPUT_RATIO",
    
    # Inter-arrival time statistics
    "AVG_IAT",
    "STD_IAT",
    "CV_IAT",
    "MIN_IAT",
    "MAX_IAT",
    "AVG_FWD_IAT",
    "AVG_BWD_IAT",
    
    # Packet size statistics
    "PKT_SIZE_MEAN",
    "PKT_SIZE_STD",
    "PKT_SIZE_SKEW",
    "PKT_SIZE_ENTROPY",
    
    # TCP flag ratios
    "SYN_TO_ACK_RATIO",
    "RST_RATE",
    "FIN_RATE",
    "PSH_RATE",
    
    # Port entropy
    "PORT_ENTROPY",
]

# All features that flow_features.py can compute (43 original + 19 enhanced = 62)
ALL_COMPUTABLE_FEATURES: list[str] = CANONICAL_FEATURES + ENHANCED_FEATURES

# Features that the model expects but cannot be reliably computed from live traffic
MISSING_FEATURES: list[str] = []

# Features that are present in both training and live, but may have different distributions
FEATURES_WITH_DISTRIBUTION_SHIFT: list[str] = [
    "L4_DST_PORT",
    "L4_SRC_PORT",
    "PROTOCOL",
    "L7_PROTO",
    "TCP_FLAGS",
    "CLIENT_TCP_FLAGS",
    "SERVER_TCP_FLAGS",
]

# Canonical feature schema with metadata
FEATURE_SCHEMA: dict[str, dict] = {
    # Core flow identifiers
    "IPV4_SRC_ADDR": {"type": "numeric", "unit": "int", "description": "Source IPv4 address as integer"},
    "L4_SRC_PORT": {"type": "numeric", "unit": "port", "description": "Source layer-4 port"},
    "IPV4_DST_ADDR": {"type": "numeric", "unit": "int", "description": "Destination IPv4 address as integer"},
    "L4_DST_PORT": {"type": "numeric", "unit": "port", "description": "Destination layer-4 port"},
    "PROTOCOL": {"type": "numeric", "unit": "enum", "description": "IP protocol (6=TCP, 17=UDP, 1=ICMP)"},
    "L7_PROTO": {"type": "numeric", "unit": "enum", "description": "Layer-7 protocol"},
    
    # Byte/packet counts
    "IN_BYTES": {"type": "numeric", "unit": "bytes", "description": "Forward direction bytes"},
    "IN_PKTS": {"type": "numeric", "unit": "count", "description": "Forward direction packets"},
    "OUT_BYTES": {"type": "numeric", "unit": "bytes", "description": "Backward direction bytes"},
    "OUT_PKTS": {"type": "numeric", "unit": "count", "description": "Backward direction packets"},
    
    # TCP flags
    "TCP_FLAGS": {"type": "numeric", "unit": "bitmask", "description": "TCP flags bitmask"},
    "CLIENT_TCP_FLAGS": {"type": "numeric", "unit": "bitmask", "description": "Client-side TCP flags"},
    "SERVER_TCP_FLAGS": {"type": "numeric", "unit": "bitmask", "description": "Server-side TCP flags"},
    
    # Duration
    "FLOW_DURATION_MILLISECONDS": {"type": "numeric", "unit": "ms", "description": "Flow duration in milliseconds"},
    "DURATION_IN": {"type": "numeric", "unit": "ms", "description": "Inbound duration"},
    "DURATION_OUT": {"type": "numeric", "unit": "ms", "description": "Outbound duration"},
    
    # TTL
    "MIN_TTL": {"type": "numeric", "unit": "ttl", "description": "Minimum TTL"},
    "MAX_TTL": {"type": "numeric", "unit": "ttl", "description": "Maximum TTL"},
    
    # Packet lengths
    "LONGEST_FLOW_PKT": {"type": "numeric", "unit": "bytes", "description": "Longest packet in flow"},
    "SHORTEST_FLOW_PKT": {"type": "numeric", "unit": "bytes", "description": "Shortest packet in flow"},
    "MIN_IP_PKT_LEN": {"type": "numeric", "unit": "bytes", "description": "Minimum IP packet length"},
    "MAX_IP_PKT_LEN": {"type": "numeric", "unit": "bytes", "description": "Maximum IP packet length"},
    
    # Second bytes
    "SRC_TO_DST_SECOND_BYTES": {"type": "numeric", "unit": "bytes", "description": "Src->dst bytes in second"},
    "DST_TO_SRC_SECOND_BYTES": {"type": "numeric", "unit": "bytes", "description": "Dst->src bytes in second"},
    
    # Retransmissions
    "RETRANSMITTED_IN_BYTES": {"type": "numeric", "unit": "bytes", "description": "Retransmitted inbound bytes"},
    "RETRANSMITTED_IN_PKTS": {"type": "numeric", "unit": "count", "description": "Retransmitted inbound packets"},
    "RETRANSMITTED_OUT_BYTES": {"type": "numeric", "unit": "bytes", "description": "Retransmitted outbound bytes"},
    "RETRANSMITTED_OUT_PKTS": {"type": "numeric", "unit": "count", "description": "Retransmitted outbound packets"},
    
    # Throughput
    "SRC_TO_DST_AVG_THROUGHPUT": {"type": "numeric", "unit": "bytes/sec", "description": "Src->dst average throughput"},
    "DST_TO_SRC_AVG_THROUGHPUT": {"type": "numeric", "unit": "bytes/sec", "description": "Dst->src average throughput"},
    
    # Packet size distribution
    "NUM_PKTS_UP_TO_128_BYTES": {"type": "numeric", "unit": "count", "description": "Packets <= 128 bytes"},
    "NUM_PKTS_128_TO_256_BYTES": {"type": "numeric", "unit": "count", "description": "Packets 128-256 bytes"},
    "NUM_PKTS_256_TO_512_BYTES": {"type": "numeric", "unit": "count", "description": "Packets 256-512 bytes"},
    "NUM_PKTS_512_TO_1024_BYTES": {"type": "numeric", "unit": "count", "description": "Packets 512-1024 bytes"},
    "NUM_PKTS_1024_TO_1514_BYTES": {"type": "numeric", "unit": "count", "description": "Packets 1024-1514 bytes"},
    
    # TCP window
    "TCP_WIN_MAX_IN": {"type": "numeric", "unit": "bytes", "description": "Max inbound TCP window"},
    "TCP_WIN_MAX_OUT": {"type": "numeric", "unit": "bytes", "description": "Max outbound TCP window"},
    
    # ICMP/DNS/FTP
    "ICMP_TYPE": {"type": "numeric", "unit": "enum", "description": "ICMP type"},
    "ICMP_IPV4_TYPE": {"type": "numeric", "unit": "enum", "description": "ICMP IPv4 type"},
    "DNS_QUERY_ID": {"type": "numeric", "unit": "id", "description": "DNS query ID"},
    "DNS_QUERY_TYPE": {"type": "numeric", "unit": "enum", "description": "DNS query type"},
    "DNS_TTL_ANSWER": {"type": "numeric", "unit": "ttl", "description": "DNS TTL answer"},
    "FTP_COMMAND_RET_CODE": {"type": "numeric", "unit": "code", "description": "FTP command return code"},
    
    # Enhanced features
    "FWD_TO_BWD_PKT_RATIO": {"type": "numeric", "unit": "ratio", "description": "Forward/backward packet ratio"},
    "FWD_TO_BWD_BYTE_RATIO": {"type": "numeric", "unit": "ratio", "description": "Forward/backward byte ratio"},
    "THROUGHPUT_RATIO": {"type": "numeric", "unit": "ratio", "description": "Throughput asymmetry ratio"},
    
    "AVG_IAT": {"type": "numeric", "unit": "us", "description": "Average inter-arrival time (microseconds)"},
    "STD_IAT": {"type": "numeric", "unit": "us", "description": "Std dev of inter-arrival time"},
    "CV_IAT": {"type": "numeric", "unit": "ratio", "description": "Coefficient of variation for IAT"},
    "MIN_IAT": {"type": "numeric", "unit": "us", "description": "Minimum inter-arrival time"},
    "MAX_IAT": {"type": "numeric", "unit": "us", "description": "Maximum inter-arrival time"},
    "AVG_FWD_IAT": {"type": "numeric", "unit": "us", "description": "Average forward IAT"},
    "AVG_BWD_IAT": {"type": "numeric", "unit": "us", "description": "Average backward IAT"},
    
    "PKT_SIZE_MEAN": {"type": "numeric", "unit": "bytes", "description": "Mean packet size"},
    "PKT_SIZE_STD": {"type": "numeric", "unit": "bytes", "description": "Std dev of packet size"},
    "PKT_SIZE_SKEW": {"type": "numeric", "unit": "skew", "description": "Skewness of packet size distribution"},
    "PKT_SIZE_ENTROPY": {"type": "numeric", "unit": "bits", "description": "Shannon entropy of packet sizes"},
    
    "SYN_TO_ACK_RATIO": {"type": "numeric", "unit": "ratio", "description": "SYN/ACK flag ratio"},
    "RST_RATE": {"type": "numeric", "unit": "ratio", "description": "RST flag rate"},
    "FIN_RATE": {"type": "numeric", "unit": "ratio", "description": "FIN flag rate"},
    "PSH_RATE": {"type": "numeric", "unit": "ratio", "description": "PSH flag rate"},
    
    "PORT_ENTROPY": {"type": "numeric", "unit": "bits", "description": "Port category entropy"},
}

# Canonical feature names in correct order (matching model's feature_names.json)
CANONICAL_FEATURE_NAMES = CANONICAL_FEATURES.copy()


def get_canonical_features() -> list[str]:
    """Return the list of canonical feature names in the correct order."""
    return CANONICAL_FEATURE_NAMES.copy()


def get_feature_schema() -> dict:
    """Return the full feature schema with metadata."""
    return FEATURE_SCHEMA.copy()


def validate_feature_set(features: list[str]) -> tuple[bool, list[str], list[str]]:
    """
    Validate a feature set against the canonical schema.
    
    Returns:
        (is_valid, missing_features, extra_features)
    """
    canonical_set = set(CANONICAL_FEATURE_NAMES)
    provided_set = set(features)
    
    missing = canonical_set - provided_set
    extra = provided_set - canonical_set
    
    is_valid = len(missing) == 0 and len(extra) == 0
    return is_valid, sorted(missing), sorted(extra)


def get_missing_features() -> list[str]:
    """Return the list of features that are missing from live capture."""
    return MISSING_FEATURES.copy()


def get_computable_missing_features() -> list[str]:
    """Return the list of features that can be computed but are currently missing."""
    return []


def get_enhanced_features() -> list[str]:
    """Return the list of enhanced features available from live capture."""
    return ENHANCED_FEATURES.copy()


def get_all_computable_features() -> list[str]:
    """Return all features computable from live traffic."""
    return ALL_COMPUTABLE_FEATURES.copy()