"""
The prediction pipeline: wires validator.py -> Predictor's scaler/PCA/model
-> confidence.py -> severity.py into the one function every other service
(and eventually the FastAPI layer) should call.

    Input Features
        v
    Validation          (validator.py)
        v
    Scaler              (predictor.scaler, fitted in Milestone 2)
        v
    PCA                 (predictor.pca, fitted in Milestone 2)
        v
    Random Forest        (predictor.model, trained in Milestone 2)
        v
    Prediction + Confidence  (confidence.py)
        v
    Attack Label          (predictor.decode_label())
        v
    Severity Level          (severity.py)

Every exception this module can raise is a subclass of PredictionError, so
a caller only needs one except clause to handle "something went wrong" -
inspecting the concrete subclass (or its .errors, for validation failures)
gives the detail.
"""

from __future__ import annotations

import time
from typing import Optional

from backend.ml import confidence as confidence_mod
from backend.ml import severity as severity_mod
from backend.ml import validator
from backend.ml.predictor import Predictor, get_predictor
from backend.ml.schemas import PredictionResponse
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class PredictionError(Exception):
    """Base class for every error inference.predict() can raise."""


class FeatureValidationFailed(PredictionError):
    """Wraps validator.FeatureValidationError so callers only need to catch PredictionError."""

    def __init__(self, validation_error: validator.FeatureValidationError):
        self.errors = validation_error.errors
        super().__init__(str(validation_error))


class InferencePipelineError(PredictionError):
    """Raised when the model/scaler/PCA pipeline itself fails on an already-validated input."""


def predict(
    features: dict,
    predictor: Optional[Predictor] = None,
    severity_map: Optional[dict[str, str]] = None,
) -> PredictionResponse:
    """
    Run one raw feature dict through the full detection pipeline.

    Args:
        features: Raw feature name -> value, matching
            `predictor.expected_features` (the trained scaler's input
            columns - see Predictor.expected_features).
        predictor: Which loaded model to use. Defaults to the process-wide
            singleton (get_predictor()) - pass one explicitly only for
            testing against a specific model version.
        severity_map: Optional override for attack-type -> severity
            lookups. Defaults to severity.DEFAULT_SEVERITY_MAP.

    Returns:
        A PredictionResponse with the predicted label, confidence,
        severity, serving model version, and processing latency.

    Raises:
        FeatureValidationFailed: If `features` is missing required
            columns, has unexpected columns, or contains a non-numeric,
            NaN, or infinite value. `.errors` holds the full list of
            ValidationErrorDetail.
        InferencePipelineError: If validation passed but the underlying
            scaler/PCA/model pipeline itself raised (e.g. a corrupted
            artifact) - wraps the original exception.
    """
    start = time.perf_counter()
    active_predictor = predictor if predictor is not None else get_predictor()

    try:
        validator.validate_and_raise(features, active_predictor.expected_features)
    except validator.FeatureValidationError as exc:
        logger.warning("Prediction rejected: %d validation error(s)", len(exc.errors))
        raise FeatureValidationFailed(exc) from exc

    try:
        X = validator.build_ordered_frame(features, active_predictor.expected_features)
        X_transformed = active_predictor.transform(X)

        raw_prediction, confidence_pct = confidence_mod.compute_confidence(active_predictor.model, X_transformed)
        attack_label = active_predictor.decode_label(raw_prediction)
        severity_level = severity_mod.get_severity(attack_label, severity_map)
    except FeatureValidationFailed:
        raise
    except Exception as exc:  # noqa: BLE001 - deliberately broad: any pipeline failure becomes one clean error type
        logger.exception("Inference pipeline failed after validation passed")
        raise InferencePipelineError(f"Prediction pipeline failed: {exc}") from exc

    latency_ms = (time.perf_counter() - start) * 1000

    response = PredictionResponse(
        prediction=attack_label,
        confidence=confidence_pct,
        severity=severity_level,
        model_version=active_predictor.version_label,
        latency_ms=round(latency_ms, 3),
    )

    logger.info(
        "Prediction served: result=%s, confidence=%.2f%%, severity=%s, model_version=%s, latency_ms=%.3f",
        response.prediction,
        response.confidence,
        response.severity,
        response.model_version,
        response.latency_ms,
    )
    return response
