"""
Flow -> CIC-IDS2017-style feature dict.

WHAT'S RECONSTRUCTED (computed directly from packet timing/size/flags,
matching CICFlowMeter's definitions closely enough to be a reasonable
approximation):

    Flow Duration, Total Fwd/Bwd Packets, Total Length of Fwd/Bwd Packets,
    Fwd/Bwd Packet Length Max/Min/Mean/Std, Flow Bytes/s, Flow Packets/s,
    Flow IAT Mean/Std/Max/Min, Fwd/Bwd IAT Total/Mean/Std/Max/Min,
    Fwd/Bwd Header Length, Fwd/Bwd Packets/s, Min/Max Packet Length,
    Packet Length Mean/Std/Variance, FIN/SYN/RST/PSH/ACK/URG Flag Count,
    Fwd/Bwd PSH/URG Flags, Down/Up Ratio, Average Packet Size,
    Avg Fwd/Bwd Segment Size.

WHAT IS **NOT** RECONSTRUCTED, AND WHY (this is the honest gap flagged
back in the Phase 1 analysis - live packet capture cannot cheaply recover
these without extra state CICFlowMeter tracks internally):

    - Init_Win_bytes_forward/backward: the TCP initial window size from the
      SYN packet's Window field specifically. Recoverable in principle (it's
      right there in the first SYN), but not implemented in this milestone
      since it requires distinguishing "the very first packet of the flow"
      from later packets with certainty, which matters more for TCP flows
      that started before capture began (no SYN was ever seen) - deferred
      rather than silently wrong.
    - Active/Idle Mean/Std/Max/Min: CICFlowMeter defines "active" periods as
      bursts of traffic separated by idle gaps above a threshold, computed
      via a specific sub-windowing algorithm over the flow's lifetime. This
      is genuinely nontrivial to replicate correctly and was deliberately
      left out of Milestone 5's scope rather than shipped as an approximation
      that looks plausible but is quietly wrong.
    - Subflow Fwd/Bwd Packets/Bytes: CICFlowMeter subdivides a flow into
      "subflows" using the same active/idle windowing above - same reason.
    - act_data_pkt_fwd, min_seg_size_forward, Fwd/Bwd Avg Bytes/Bulk,
      Fwd/Bwd Avg Packets/Bulk, Fwd/Bwd Avg Bulk Rate: CICFlowMeter-specific
      bulk-transfer detection heuristics, not implemented here.

Every feature in the second list, if the trained model requires it, is
filled with a documented default (0.0) by feature_mapper.py - not silently
dropped. See feature_mapper.py's module docstring for how that's surfaced
to logs, and the Milestone 5 documentation (README) for the accuracy
implication of relying on these defaults.
"""

from __future__ import annotations

import statistics
from typing import Optional

from backend.packet_capture.flow_manager import Flow

# CIC-IDS2017's Flow Duration and *_IAT_* columns are in **microseconds**,
# not seconds - this constant converts the flow's second-resolution
# timestamps to match, so the model sees the same units it was trained on.
_SECONDS_TO_MICROSECONDS = 1_000_000


def _mean(values: list[float]) -> float:
    return statistics.fmean(values) if values else 0.0


def _std(values: list[float]) -> float:
    return statistics.pstdev(values) if len(values) > 1 else 0.0


def _inter_arrival_times(timestamps: list[float]) -> list[float]:
    """Consecutive gaps between sorted timestamps, in microseconds."""
    if len(timestamps) < 2:
        return []
    ordered = sorted(timestamps)
    return [(b - a) * _SECONDS_TO_MICROSECONDS for a, b in zip(ordered, ordered[1:])]


def extract_flow_features(flow: Flow) -> dict[str, float]:
    """
    Compute the reconstructable CIC-IDS2017-style feature set for one
    completed (or in-progress, if called early) Flow.

    Returns:
        A flat dict of feature name -> float. Only includes the features
        listed as "reconstructed" in this module's docstring - anything
        else the trained model needs is the caller's responsibility (see
        feature_mapper.map_to_model_features()).
    """
    duration_seconds = max(0.0, flow.last_seen - flow.start_time)
    duration_us = duration_seconds * _SECONDS_TO_MICROSECONDS

    fwd_lengths = flow.fwd_lengths
    bwd_lengths = flow.bwd_lengths
    all_lengths = fwd_lengths + bwd_lengths

    total_packets = len(all_lengths)
    total_bytes = sum(all_lengths)

    all_timestamps = flow.fwd_timestamps + flow.bwd_timestamps
    flow_iat = _inter_arrival_times(all_timestamps)
    fwd_iat = _inter_arrival_times(flow.fwd_timestamps)
    bwd_iat = _inter_arrival_times(flow.bwd_timestamps)

    features: dict[str, float] = {
        "Flow Duration": duration_us,
        "Total Fwd Packets": float(len(fwd_lengths)),
        "Total Backward Packets": float(len(bwd_lengths)),
        "Total Length of Fwd Packets": float(sum(fwd_lengths)),
        "Total Length of Bwd Packets": float(sum(bwd_lengths)),

        "Fwd Packet Length Max": float(max(fwd_lengths)) if fwd_lengths else 0.0,
        "Fwd Packet Length Min": float(min(fwd_lengths)) if fwd_lengths else 0.0,
        "Fwd Packet Length Mean": _mean(fwd_lengths),
        "Fwd Packet Length Std": _std(fwd_lengths),
        "Bwd Packet Length Max": float(max(bwd_lengths)) if bwd_lengths else 0.0,
        "Bwd Packet Length Min": float(min(bwd_lengths)) if bwd_lengths else 0.0,
        "Bwd Packet Length Mean": _mean(bwd_lengths),
        "Bwd Packet Length Std": _std(bwd_lengths),

        "Flow Bytes/s": (total_bytes / duration_seconds) if duration_seconds > 0 else 0.0,
        "Flow Packets/s": (total_packets / duration_seconds) if duration_seconds > 0 else 0.0,
        "Fwd Packets/s": (len(fwd_lengths) / duration_seconds) if duration_seconds > 0 else 0.0,
        "Bwd Packets/s": (len(bwd_lengths) / duration_seconds) if duration_seconds > 0 else 0.0,

        "Flow IAT Mean": _mean(flow_iat),
        "Flow IAT Std": _std(flow_iat),
        "Flow IAT Max": float(max(flow_iat)) if flow_iat else 0.0,
        "Flow IAT Min": float(min(flow_iat)) if flow_iat else 0.0,

        "Fwd IAT Total": float(sum(fwd_iat)),
        "Fwd IAT Mean": _mean(fwd_iat),
        "Fwd IAT Std": _std(fwd_iat),
        "Fwd IAT Max": float(max(fwd_iat)) if fwd_iat else 0.0,
        "Fwd IAT Min": float(min(fwd_iat)) if fwd_iat else 0.0,

        "Bwd IAT Total": float(sum(bwd_iat)),
        "Bwd IAT Mean": _mean(bwd_iat),
        "Bwd IAT Std": _std(bwd_iat),
        "Bwd IAT Max": float(max(bwd_iat)) if bwd_iat else 0.0,
        "Bwd IAT Min": float(min(bwd_iat)) if bwd_iat else 0.0,

        "Fwd PSH Flags": float(flow.fwd_psh),
        "Bwd PSH Flags": float(flow.bwd_psh),
        "Fwd URG Flags": float(flow.fwd_urg),
        "Bwd URG Flags": float(flow.bwd_urg),

        "Fwd Header Length": float(flow.fwd_header_bytes),
        "Bwd Header Length": float(flow.bwd_header_bytes),

        "Min Packet Length": float(min(all_lengths)) if all_lengths else 0.0,
        "Max Packet Length": float(max(all_lengths)) if all_lengths else 0.0,
        "Packet Length Mean": _mean([float(x) for x in all_lengths]),
        "Packet Length Std": _std([float(x) for x in all_lengths]),
        "Packet Length Variance": _std([float(x) for x in all_lengths]) ** 2,

        "FIN Flag Count": float(flow.flag_counts.get("FIN", 0)),
        "SYN Flag Count": float(flow.flag_counts.get("SYN", 0)),
        "RST Flag Count": float(flow.flag_counts.get("RST", 0)),
        "PSH Flag Count": float(flow.flag_counts.get("PSH", 0)),
        "ACK Flag Count": float(flow.flag_counts.get("ACK", 0)),
        "URG Flag Count": float(flow.flag_counts.get("URG", 0)),

        "Down/Up Ratio": (len(bwd_lengths) / len(fwd_lengths)) if fwd_lengths else 0.0,
        "Average Packet Size": _mean([float(x) for x in all_lengths]),
        "Avg Fwd Segment Size": _mean([float(x) for x in fwd_lengths]),
        "Avg Bwd Segment Size": _mean([float(x) for x in bwd_lengths]),
    }

    return features
