"""
Live Packet Features -> Model Features.

`flow_features.extract_flow_features()` computes what it can from live
traffic. This module reconciles that against `predictor.expected_features`
(the trained model's exact required input columns - see
backend.ml.predictor.Predictor.expected_features), filling any feature the
live pipeline cannot reconstruct with a documented default rather than
raising, and dropping anything live-computed that the model doesn't
actually use.

Filling with a default is a deliberate, visible approximation, not a
silent one: every fill is counted, and a single aggregated warning is
logged per flow (not one log line per missing feature, which would be
noise at scale) - see build_feature_mapping_report().
"""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.utils.logger import get_logger

logger = get_logger(__name__)

# Applied to any expected feature with no live-computed value. 0.0 is a
# neutral choice post-StandardScaler (roughly "average", since the scaler
# centers each feature at 0) - not "correct", just the least-misleading
# constant available without the deeper CICFlowMeter logic documented in
# flow_features.py's module docstring.
DEFAULT_FILL_VALUE = 0.0


@dataclass
class FeatureMappingReport:
    """What happened when mapping one flow's live features onto the model's expected input."""

    matched: list[str] = field(default_factory=list)
    filled_with_default: list[str] = field(default_factory=list)
    dropped_unused: list[str] = field(default_factory=list)

    @property
    def coverage_ratio(self) -> float:
        """Fraction of the model's expected features that were actually reconstructed from live traffic."""
        total = len(self.matched) + len(self.filled_with_default)
        return (len(self.matched) / total) if total else 1.0


def map_to_model_features(
    live_features: dict[str, float],
    expected_features: list[str],
) -> tuple[dict[str, float], FeatureMappingReport]:
    """
    Reindex `live_features` to exactly `expected_features`, in order,
    filling gaps with DEFAULT_FILL_VALUE.

    Args:
        live_features: Output of flow_features.extract_flow_features().
        expected_features: predictor.expected_features - the trained
            scaler's exact input column names/order.

    Returns:
        (mapped_features, report) - `mapped_features` is ready to hand to
        backend.ml.validator / inference.predict() as-is; `report` records
        what was matched vs. defaulted, for logging and (later) surfacing
        confidence caveats to the UI.
    """
    report = FeatureMappingReport()
    mapped: dict[str, float] = {}

    for name in expected_features:
        if name in live_features:
            mapped[name] = live_features[name]
            report.matched.append(name)
        else:
            mapped[name] = DEFAULT_FILL_VALUE
            report.filled_with_default.append(name)

    report.dropped_unused = sorted(set(live_features) - set(expected_features))

    if report.filled_with_default:
        logger.warning(
            "Flow feature mapping: %d/%d expected feature(s) defaulted to %.1f (coverage=%.1f%%): %s",
            len(report.filled_with_default),
            len(expected_features),
            DEFAULT_FILL_VALUE,
            report.coverage_ratio * 100,
            report.filled_with_default,
        )

    return mapped, report
