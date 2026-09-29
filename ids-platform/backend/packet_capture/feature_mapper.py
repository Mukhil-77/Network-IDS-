"""
Live Packet Features -> Model Features.

`flow_features.extract_flow_features()` computes what it can from live
traffic. This module reconciles that against the canonical feature schema
(see `backend.ml.feature_schema.CANONICAL_FEATURE_NAMES`), raising an error
for any feature the live pipeline cannot reconstruct, and dropping anything
live-computed that the model doesn't actually use.

Raising an error for missing features ensures we never silently zero-fill
features the model was trained on but the live pipeline cannot reconstruct.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.ml.feature_schema import CANONICAL_FEATURE_NAMES
from backend.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class FeatureMappingReport:
    """What happened when mapping one flow's live features onto the model's expected input."""

    matched: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    dropped_unused: list[str] = field(default_factory=list)

    @property
    def coverage_ratio(self) -> float:
        """Fraction of the model's expected features that were actually reconstructed from live traffic."""
        total = len(self.matched) + len(self.missing)
        return (len(self.matched) / total) if total else 1.0


def map_to_model_features(
    live_features: dict[str, float],
    expected_features: list[str] | None = None,
) -> tuple[dict[str, float], FeatureMappingReport]:
    """
    Reindex `live_features` to exactly the canonical feature set, in order,
    raising an error for any feature the live pipeline cannot reconstruct.

    Args:
        live_features: Output of flow_features.extract_flow_features().
        expected_features: Optional override of the expected feature list.
            Defaults to the canonical feature set.

    Returns:
        (mapped_features, report) - `mapped_features` is ready to hand to
        backend.ml.validator / inference.predict() as-is; `report` records
        what was matched vs. missing, for logging and (later) surfacing
        confidence caveats to the UI.

    Raises:
        ValueError: If any expected feature is missing from live_features.
    """
    if expected_features is None:
        expected_features = CANONICAL_FEATURE_NAMES

    report = FeatureMappingReport()
    mapped: dict[str, float] = {}

    for name in expected_features:
        if name in live_features:
            mapped[name] = live_features[name]
            report.matched.append(name)
        else:
            report.missing.append(name)

    report.dropped_unused = sorted(set(live_features) - set(expected_features))

    if report.missing:
        logger.error(
            "Flow feature mapping: %d/%d expected feature(s) MISSING (coverage=%.1f%%): %s",
            len(report.missing),
            len(expected_features),
            (len(report.matched) / len(expected_features)) * 100 if expected_features else 0,
            report.missing,
        )
        raise ValueError(
            f"Missing features in live flow data: {report.missing}. "
            f"Cannot proceed with inference. Expected {len(expected_features)} features, "
            f"got {len(report.matched)}. Missing: {report.missing}"
        )

    if report.dropped_unused:
        logger.warning(
            "Flow feature mapping: %d live-computed feature(s) not used by model: %s",
            len(report.dropped_unused),
            report.dropped_unused,
        )

    if report.missing:
        logger.error(
            "Flow feature mapping coverage: %.1f%% (%d/%d features present)",
            len(report.matched) / len(expected_features) * 100,
            len(report.matched),
            len(expected_features),
        )

    return mapped, report
