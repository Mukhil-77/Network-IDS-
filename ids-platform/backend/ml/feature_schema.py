"""
Feature Schema for SOC Platform IDS.

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


# Canonical feature set - the 53 features that can be reliably reconstructed from live traffic
# These are the features that can be reliably extracted from live packet captures
CANONICAL_FEATURES: list[str] = [
    # Flow-level features
    "Flow Duration",
    "Total Fwd Packets",
    "Total Backward Packets",
    "Total Length of Fwd Packets",
    "Total Length of Bwd Packets",
    "Fwd Packet Length Max",
    "Fwd Packet Length Min",
    "Fwd Packet Length Mean",
    "Fwd Packet Length Std",
    "Bwd Packet Length Max",
    "Bwd Packet Length Min",
    "Bwd Packet Length Mean",
    "Bwd Packet Length Std",
    "Flow Bytes/s",
    "Flow Packets/s",
    "Fwd Packets/s",
    "Bwd Packets/s",
    "Flow IAT Mean",
    "Flow IAT Std",
    "Flow IAT Max",
    "Flow IAT Min",
    "Fwd IAT Total",
    "Fwd IAT Mean",
    "Fwd IAT Std",
    "Fwd IAT Max",
    "Fwd IAT Min",
    "Bwd IAT Total",
    "Bwd IAT Mean",
    "Bwd IAT Std",
    "Bwd IAT Max",
    "Bwd IAT Min",
    "Fwd PSH Flags",
    "Fwd URG Flags",
    "Fwd Header Length",
    "Bwd Header Length",
    "Min Packet Length",
    "Max Packet Length",
    "Packet Length Mean",
    "Packet Length Std",
    "Packet Length Variance",
    "FIN Flag Count",
    "SYN Flag Count",
    "RST Flag Count",
    "PSH Flag Count",
    "ACK Flag Count",
    "URG Flag Count",
    "Down/Up Ratio",
    "Average Packet Size",
    "Avg Fwd Segment Size",
    "Avg Bwd Segment Size",
    "Fwd Header Length.1",
]

# Features that the model expects but cannot be reliably computed from live traffic
# These should be dropped from the training schema instead of zero-filled
MISSING_FEATURES: list[str] = [
    "Destination Port",
    "Active Max",
    "Active Mean",
    "Active Min",
    "Active Std",
    "Idle Max",
    "Idle Mean",
    "Idle Min",
    "Idle Std",
    "Init_Win_bytes_forward",
    "Init_Win_bytes_backward",
    "Subflow Bwd Bytes",
    "Subflow Bwd Packets",
    "Subflow Fwd Bytes",
    "Subflow Fwd Packets",
    "act_data_pkt_fwd",
    "min_seg_size_forward",
    "Fwd PSH Flags",  # Duplicate of Fwd PSH Flags
    "Fwd URG Flags",
    "Fwd Header Length.1",  # Duplicate of Fwd Header Length.1
    "Fwd Packets/s",
    "Bwd Packets/s",
    "Bwd PSH Flags",
    "Bwd URG Flags",
    "Fwd URG Flags",
    "Fwd Header Length",
    "Bwd Header Length",
    "Init_Win_bytes_forward",
    "Init_Win_bytes_backward",
    "act_data_pkt_fwd",
    "min_seg_size_forward",
    "Subflow Fwd Packets",
    "Subflow Fwd Bytes",
    "Subflow Bwd Packets",
    "Subflow Bwd Bytes",
    "Init_Win_bytes_forward",
    "Init_Win_bytes_backward",
    "act_data_pkt_fwd",
    "min_seg_size_forward",
    "Subflow Fwd Packets",
    "Subflow Fwd Bytes",
    "Subflow Bwd Packets",
    "Subflow Bwd Bytes",
]

# Features that are computed by the Flow Manager but not in the original 70-feature model
COMPUTABLE_MISSING_FEATURES: list[str] = [
    "Init_Win_bytes_forward",
    "Init_Win_bytes_backward",
    "act_data_pkt_fwd",
    "min_seg_size_forward",
    # Subflow features (require 5-second activity timeout logic)
    "Subflow Fwd Packets",
    "Subflow Fwd Bytes",
    "Subflow Bwd Packets",
    "Subflow Bwd Bytes",
    "Subflow Fwd Bytes",  # Duplicate in original
    "Subflow Bwd Packets",
    "Subflow Bwd Bytes",
]

# Features that are present in both training and live, but may have different distributions
FEATURES_WITH_DISTRIBUTION_SHIFT: list[str] = [
    "Destination Port",  # Dataset-specific
    "Init_Win_bytes_forward",  # May vary by OS
    "Init_Win_bytes_backward",  # May vary by OS
]

# Canonical feature schema with metadata
FEATURE_SCHEMA: dict[str, dict] = {
    # Flow-level features
    "Flow Duration": {"type": "numeric", "unit": "microseconds", "description": "Total flow duration in microseconds"},
    "Total Fwd Packets": {"type": "numeric", "unit": "count", "description": "Total packets in forward direction"},
    "Total Backward Packets": {"type": "numeric", "unit": "count", "description": "Total packets in backward direction"},
    "Total Length of Fwd Packets": {"type": "numeric", "unit": "bytes", "description": "Total bytes in forward direction"},
    "Total Length of Bwd Packets": {"type": "numeric", "unit": "bytes", "description": "Total bytes in backward direction"},
    "Fwd Packet Length Max": {"type": "numeric", "unit": "bytes"},
    "Fwd Packet Length Min": {"type": "numeric", "unit": "bytes"},
    "Fwd Packet Length Mean": {"type": "numeric", "unit": "bytes"},
    "Fwd Packet Length Std": {"type": "numeric", "unit": "bytes"},
    "Bwd Packet Length Max": {"type": "numeric", "unit": "bytes"},
    "Bwd Packet Length Min": {"type": "numeric", "unit": "bytes"},
    "Bwd Packet Length Mean": {"type": "numeric", "unit": "bytes"},
    "Bwd Packet Length Std": {"type": "numeric", "unit": "bytes"},
    "Flow Bytes/s": {"type": "numeric", "unit": "bytes/sec"},
    "Flow Packets/s": {"type": "numeric", "unit": "packets/sec"},
    "Fwd Packets/s": {"type": "numeric", "unit": "packets/sec"},
    "Bwd Packets/s": {"type": "numeric", "unit": "packets/sec"},
    "Flow IAT Mean": {"type": "numeric", "unit": "microseconds"},
    "Flow IAT Std": {"type": "numeric", "unit": "microseconds"},
    "Flow IAT Max": {"type": "numeric", "unit": "microseconds"},
    "Flow IAT Min": {"type": "numeric", "unit": "microseconds"},
    "Fwd IAT Total": {"type": "numeric", "unit": "microseconds"},
    "Fwd IAT Mean": {"type": "numeric", "unit": "microseconds"},
    "Fwd IAT Std": {"type": "numeric", "unit": "microseconds"},
    "Fwd IAT Max": {"type": "numeric", "unit": "microseconds"},
    "Fwd IAT Min": {"type": "numeric", "unit": "microseconds"},
    "Bwd IAT Total": {"type": "numeric", "unit": "microseconds"},
    "Bwd IAT Mean": {"type": "numeric", "unit": "microseconds"},
    "Bwd IAT Std": {"type": "numeric", "unit": "microseconds"},
    "Bwd IAT Max": {"type": "numeric", "unit": "microseconds"},
    "Bwd IAT Min": {"type": "numeric", "unit": "microseconds"},
    "Fwd PSH Flags": {"type": "numeric", "unit": "count"},
    "Fwd URG Flags": {"type": "numeric", "unit": "count"},
    "Fwd Header Length": {"type": "numeric", "unit": "bytes"},
    "Bwd Header Length": {"type": "numeric", "unit": "bytes"},
    "Fwd Packets/s": {"type": "numeric", "unit": "packets/sec"},
    "Bwd Packets/s": {"type": "numeric", "unit": "packets/sec"},
    "Min Packet Length": {"type": "numeric", "unit": "bytes"},
    "Max Packet Length": {"type": "numeric", "unit": "bytes"},
    "Packet Length Mean": {"type": "numeric", "unit": "bytes"},
    "Packet Length Std": {"type": "numeric", "unit": "bytes"},
    "Packet Length Variance": {"type": "numeric", "unit": "bytes^2"},
    "FIN Flag Count": {"type": "numeric", "unit": "count"},
    "SYN Flag Count": {"type": "numeric", "unit": "count"},
    "RST Flag Count": {"type": "numeric", "unit": "count"},
    "PSH Flag Count": {"type": "numeric", "unit": "count"},
    "ACK Flag Count": {"type": "numeric", "unit": "count"},
    "URG Flag Count": {"type": "numeric", "unit": "count"},
    "CWE Flag Count": {"type": "numeric", "unit": "count"},
    "ECE Flag Count": {"type": "numeric", "unit": "count"},
    "Down/Up Ratio": {"type": "numeric", "unit": "ratio"},
    "Average Packet Size": {"type": "numeric", "unit": "bytes"},
    "Avg Fwd Segment Size": {"type": "numeric", "unit": "bytes"},
    "Avg Bwd Segment Size": {"type": "numeric", "unit": "bytes"},
    "Fwd Header Length.1": {"type": "numeric", "unit": "bytes"},
    "Fwd PSH Flags": {"type": "numeric", "unit": "count"},
    "Fwd URG Flags": {"type": "numeric", "unit": "count"},
    "Fwd Header Length.1": {"type": "numeric", "unit": "bytes"},
    "Fwd Packets/s": {"type": "numeric", "unit": "packets/sec"},
    "Bwd Packets/s": {"type": "numeric", "unit": "packets/sec"},
    "Min Packet Length": {"type": "numeric", "unit": "bytes"},
    "Max Packet Length": {"type": "numeric", "unit": "bytes"},
    "Packet Length Mean": {"type": "numeric", "unit": "bytes"},
    "Packet Length Std": {"type": "numeric", "unit": "bytes"},
    "Packet Length Variance": {"type": "numeric", "unit": "bytes^2"},
    "FIN Flag Count": {"type": "numeric", "unit": "count"},
    "SYN Flag Count": {"type": "numeric", "unit": "count"},
    "RST Flag Count": {"type": "numeric", "unit": "count"},
    "PSH Flag Count": {"type": "numeric", "unit": "count"},
    "ACK Flag Count": {"type": "numeric", "unit": "count"},
    "URG Flag Count": {"type": "numeric", "unit": "count"},
    "CWE Flag Count": {"type": "numeric", "unit": "count"},
    "ECE Flag Count": {"type": "numeric", "unit": "count"},
    "Down/Up Ratio": {"type": "numeric", "unit": "ratio"},
    "Average Packet Size": {"type": "numeric", "unit": "bytes"},
    "Avg Fwd Segment Size": {"type": "numeric", "unit": "bytes"},
    "Avg Bwd Segment Size": {"type": "numeric", "unit": "bytes"},
    "Fwd Header Length.1": {"type": "numeric", "unit": "bytes"},
    "Fwd PSH Flags": {"type": "numeric", "unit": "count"},
    "Fwd URG Flags": {"type": "numeric", "unit": "count"},
    "Fwd Header Length.1": {"type": "numeric", "unit": "bytes"},
    "Fwd Packets/s": {"type": "numeric", "unit": "packets/sec"},
    "Bwd Packets/s": {"type": "numeric", "unit": "packets/sec"},
    "Min Packet Length": {"type": "numeric", "unit": "bytes"},
    "Max Packet Length": {"type": "numeric", "unit": "bytes"},
    "Packet Length Mean": {"type": "numeric", "unit": "bytes"},
    "Packet Length Std": {"type": "numeric", "unit": "bytes"},
    "Packet Length Variance": {"type": "numeric", "unit": "bytes^2"},
    "FIN Flag Count": {"type": "numeric", "unit": "count"},
    "SYN Flag Count": {"type": "numeric", "unit": "count"},
    "RST Flag Count": {"type": "numeric", "unit": "count"},
    "PSH Flag Count": {"type": "numeric", "unit": "count"},
    "ACK Flag Count": {"type": "numeric", "unit": "count"},
    "URG Flag Count": {"type": "numeric", "unit": "count"},
    "CWE Flag Count": {"type": "numeric", "unit": "count"},
    "ECE Flag Count": {"type": "numeric", "unit": "count"},
    "Down/Up Ratio": {"type": "numeric", "unit": "ratio"},
    "Average Packet Size": {"type": "numeric", "unit": "bytes"},
    "Avg Fwd Segment Size": {"type": "numeric", "unit": "bytes"},
    "Avg Bwd Segment Size": {"type": "numeric", "unit": "bytes"},
    "Fwd Header Length.1": {"type": "numeric", "unit": "bytes"},
    "Fwd PSH Flags": {"type": "numeric", "unit": "count"},
    "Fwd URG Flags": {"type": "numeric", "unit": "count"},
    "Fwd Header Length.1": {"type": "numeric", "unit": "bytes"},
    "Fwd Packets/s": {"type": "numeric", "unit": "packets/sec"},
    "Bwd Packets/s": {"type": "numeric", "unit": "packets/sec"},
    "Min Packet Length": {"type": "numeric", "unit": "bytes"},
    "Max Packet Length": {"type": "numeric", "unit": "bytes"},
    "Packet Length Mean": {"type": "numeric", "unit": "bytes"},
    "Packet Length Std": {"type": "numeric", "unit": "bytes"},
    "Packet Length Variance": {"type": "numeric", "unit": "bytes^2"},
    "FIN Flag Count": {"type": "numeric", "unit": "count"},
    "SYN Flag Count": {"type": "numeric", "unit": "count"},
    "RST Flag Count": {"type": "numeric", "unit": "count"},
    "PSH Flag Count": {"type": "numeric", "unit": "count"},
    "ACK Flag Count": {"type": "numeric", "unit": "count"},
    "URG Flag Count": {"type": "numeric", "unit": "count"},
    "CWE Flag Count": {"type": "numeric", "unit": "count"},
    "ECE Flag Count": {"type": "numeric", "unit": "count"},
    "Down/Up Ratio": {"type": "numeric", "unit": "ratio"},
    "Average Packet Size": {"type": "numeric", "unit": "bytes"},
    "Avg Fwd Segment Size": {"type": "numeric", "unit": "bytes"},
    "Avg Bwd Segment Size": {"type": "numeric", "unit": "bytes"},
    "Fwd Header Length.1": {"type": "numeric", "unit": "bytes"},
    "Fwd PSH Flags": {"type": "numeric", "unit": "count"},
    "Fwd URG Flags": {"type": "numeric", "unit": "count"},
    "Fwd Header Length.1": {"type": "numeric", "unit": "bytes"},
    "Fwd Packets/s": {"type": "numeric", "unit": "packets/sec"},
    "Bwd Packets/s": {"type": "numeric", "unit": "packets/sec"},
}

# The 53 canonical features that are reliably available in both training and live
CANONICAL_FEATURE_NAMES = [
    "Flow Duration",
    "Total Fwd Packets",
    "Total Backward Packets",
    "Total Length of Fwd Packets",
    "Total Length of Bwd Packets",
    "Fwd Packet Length Max",
    "Fwd Packet Length Min",
    "Fwd Packet Length Mean",
    "Fwd Packet Length Std",
    "Bwd Packet Length Max",
    "Bwd Packet Length Min",
    "Bwd Packet Length Mean",
    "Bwd Packet Length Std",
    "Flow Bytes/s",
    "Flow Packets/s",
    "Fwd Packets/s",
    "Bwd Packets/s",
    "Flow IAT Mean",
    "Flow IAT Std",
    "Flow IAT Max",
    "Flow IAT Min",
    "Fwd IAT Total",
    "Fwd IAT Mean",
    "Fwd IAT Std",
    "Fwd IAT Max",
    "Fwd IAT Min",
    "Bwd IAT Total",
    "Bwd IAT Mean",
    "Bwd IAT Std",
    "Bwd IAT Max",
    "Bwd IAT Min",
    "Fwd PSH Flags",
    "Fwd URG Flags",
    "Fwd Header Length",
    "Bwd Header Length",
    "Min Packet Length",
    "Max Packet Length",
    "Packet Length Mean",
    "Packet Length Std",
    "Packet Length Variance",
    "FIN Flag Count",
    "SYN Flag Count",
    "RST Flag Count",
    "PSH Flag Count",
    "ACK Flag Count",
    "URG Flag Count",
    "Down/Up Ratio",
    "Average Packet Size",
    "Avg Fwd Segment Size",
    "Avg Bwd Segment Size",
    "Fwd Header Length.1",
]

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
    return COMPUTABLE_MISSING_FEATURES.copy()