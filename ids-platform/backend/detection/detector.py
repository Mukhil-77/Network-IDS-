"""
Flow -> PredictionResponse.

This is deliberately the only place packet_capture's output meets
backend.ml's input. No inference/validation/confidence/severity logic is
reimplemented here - `prediction_service.predict()` (Milestone 4, which
itself is a thin wrapper over Milestones 2-3) is called exactly as the
FastAPI /predict route calls it. A live-captured flow and an API request
go through the identical pipeline from this point on.
"""

from __future__ import annotations

from backend.ml.schemas import PredictionResponse
from backend.packet_capture.flow_features import extract_flow_features
from backend.packet_capture.flow_manager import Flow
from backend.packet_capture.feature_mapper import FeatureMappingReport, map_to_model_features
from backend.services.prediction_service import PredictionService
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class Detector:
    """Wraps a PredictionService for use against live Flow objects instead of raw API requests."""

    def __init__(self, prediction_service: PredictionService):
        self.prediction_service = prediction_service

    def classify_flow(self, flow: Flow) -> tuple[PredictionResponse, FeatureMappingReport]:
        """
        Extract, map, and classify one completed flow.

        Returns:
            (prediction, mapping_report) - `mapping_report` is returned
            alongside the prediction (rather than only logged) so a caller
            can attach a "reduced confidence" caveat when coverage_ratio is
            low, without recomputing anything.

        Raises: whatever prediction_service.predict() raises - ArtifactNotFoundError
            (no model), FeatureValidationFailed (shouldn't happen post-mapping,
            since every expected feature is always present after mapping,
            but propagated rather than swallowed if it somehow does),
            InferencePipelineError.
        """
        live_features = extract_flow_features(flow)
        expected_features = self.prediction_service.get_expected_features()
        mapped_features, report = map_to_model_features(live_features, expected_features)

        prediction = self.prediction_service.predict(mapped_features)

        logger.info(
            "Flow %s classified: %s (confidence=%.2f%%, feature_coverage=%.1f%%)",
            flow.flow_id, prediction.prediction, prediction.confidence, report.coverage_ratio * 100,
        )
        return prediction, report
