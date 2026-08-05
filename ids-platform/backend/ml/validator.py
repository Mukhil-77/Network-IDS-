"""
Input validation for prediction requests.

Runs before anything touches the scaler/PCA/model, so a bad request fails
fast with a specific, actionable list of problems (schemas.ValidationErrorDetail)
rather than a raw sklearn exception (or worse, a silently wrong prediction
from NaN/inf propagating through the pipeline).

Checks performed, in order:
    1. Unexpected columns   - keys in the request not in the trained feature set
    2. Missing features     - trained feature names absent from the request
    3. Invalid datatypes    - values that aren't int/float or numeric strings
    4. NaN values
    5. Infinite values
    6. Feature order        - not a request-shape error (dict keys are unordered
                               by definition); handled by reindexing to the
                               trained order once everything above passes -
                               see build_ordered_frame().

All checks run and accumulate every problem found (rather than stopping at
the first) so a caller fixing their request sees everything wrong in one
round trip instead of one error at a time.
"""

from __future__ import annotations

import math
from numbers import Real
from typing import Any

import pandas as pd

from backend.ml.schemas import ValidationErrorDetail
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class FeatureValidationError(Exception):
    """
    Raised when one or more problems are found with a prediction request's
    features. Carries the full list of ValidationErrorDetail so a caller
    (inference.py, and eventually a FastAPI exception handler) can report
    everything at once.
    """

    def __init__(self, errors: list[ValidationErrorDetail]):
        self.errors = errors
        summary = "; ".join(f"[{e.error_type}] {e.field}: {e.message}" for e in errors)
        super().__init__(f"{len(errors)} validation error(s): {summary}")


def _is_numeric(value: Any) -> bool:
    """True if `value` is a real number, or a string that parses as one (JSON has no NaN/Infinity by default)."""
    if isinstance(value, bool):  # bool is a Real subclass in Python; explicitly reject it here
        return False
    if isinstance(value, Real):
        return True
    if isinstance(value, str):
        try:
            float(value)
            return True
        except ValueError:
            return False
    return False


def validate_features(
    features: dict[str, Any],
    expected_features: list[str],
) -> list[ValidationErrorDetail]:
    """
    Check a raw feature dict against the trained pipeline's expected input
    columns. Does not raise - returns the (possibly empty) list of problems
    found, so callers can decide how to react. Most callers should use
    validate_and_raise() instead.

    Args:
        features: Raw feature name -> value, as received in a PredictionRequest.
        expected_features: The exact feature names (and order) the trained
            scaler expects - Predictor.expected_features.

    Returns:
        List of ValidationErrorDetail, empty if the input is valid.
    """
    errors: list[ValidationErrorDetail] = []
    expected_set = set(expected_features)
    received_set = set(features.keys())

    # 1. Unexpected columns
    for extra in sorted(received_set - expected_set):
        errors.append(
            ValidationErrorDetail(
                field=extra,
                error_type="unexpected_feature",
                message=f"'{extra}' is not one of the model's trained input features.",
            )
        )

    # 2. Missing features
    for missing in sorted(expected_set - received_set):
        errors.append(
            ValidationErrorDetail(
                field=missing,
                error_type="missing_feature",
                message=f"Required feature '{missing}' was not provided.",
            )
        )

    # 3-5. Type / NaN / Infinite checks, only for features that are both
    # expected and present (missing ones are already reported above; extra
    # ones aren't worth double-checking their type).
    for name in sorted(expected_set & received_set):
        value = features[name]

        if not _is_numeric(value):
            errors.append(
                ValidationErrorDetail(
                    field=name,
                    error_type="invalid_type",
                    message=f"'{name}' must be numeric; got {type(value).__name__} ({value!r}).",
                )
            )
            continue  # can't meaningfully check NaN/inf on a non-numeric value

        numeric_value = float(value)

        if math.isnan(numeric_value):
            errors.append(
                ValidationErrorDetail(
                    field=name,
                    error_type="nan_value",
                    message=f"'{name}' is NaN, which the trained scaler cannot accept.",
                )
            )
        elif math.isinf(numeric_value):
            errors.append(
                ValidationErrorDetail(
                    field=name,
                    error_type="infinite_value",
                    message=f"'{name}' is infinite, which the trained scaler cannot accept.",
                )
            )

    return errors


def validate_and_raise(features: dict[str, Any], expected_features: list[str]) -> None:
    """Run validate_features() and raise FeatureValidationError if anything was found."""
    errors = validate_features(features, expected_features)
    if errors:
        logger.warning("Rejected prediction request: %d validation error(s)", len(errors))
        raise FeatureValidationError(errors)


def build_ordered_frame(features: dict[str, Any], expected_features: list[str]) -> pd.DataFrame:
    """
    Build a single-row DataFrame with columns in exactly `expected_features`
    order (the "feature order" check from the spec: a dict has no inherent
    order, so rather than rejecting a correctly-keyed-but-differently-typed
    dict, this reindexes it to the order the scaler was fit on).

    Callers must run validate_and_raise() first - this function assumes
    every name in `expected_features` is present in `features` and numeric.
    """
    ordered_values = {name: float(features[name]) for name in expected_features}
    return pd.DataFrame([ordered_values], columns=expected_features)
