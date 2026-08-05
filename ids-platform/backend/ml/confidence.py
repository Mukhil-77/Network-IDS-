"""
Confidence scoring for a single prediction.

Isolated from inference.py so the "how do we turn predict_proba output into
a confidence percentage" decision lives in exactly one place, and so it's
trivially unit-testable with plain arrays (no model, no scaler, no I/O).
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def compute_confidence(model, X_transformed: "np.ndarray | pd.DataFrame") -> tuple[str, float]:
    """
    Predict a label and its confidence for one (already scaled+PCA'd) row.

    Confidence is the model's own predicted probability for the winning
    class (`predict_proba(...).max()`), expressed as a percentage. This
    matches the notebook's use of `predict_proba` for its ROC/PR curves -
    same underlying probabilities, just read off for the top class instead
    of the positive-class column.

    Args:
        model: A fitted classifier exposing `.predict()` and, ideally,
            `.predict_proba()`.
        X_transformed: A single row of scaler+PCA output, shape (1, n_components)
            - either a bare ndarray or a DataFrame (Predictor.transform()
            returns a DataFrame so column names match what the model was
            trained on; either works here since sklearn accepts both).

    Returns:
        (predicted_label, confidence_percent) - confidence_percent is
        0-100, rounded to 2 decimal places.

    Raises:
        ValueError: If `X_transformed` doesn't contain exactly one row.
    """
    if X_transformed.shape[0] != 1:
        raise ValueError(f"compute_confidence expects exactly one row, got {X_transformed.shape[0]}")

    prediction = model.predict(X_transformed)[0]

    if hasattr(model, "predict_proba"):
        probabilities = model.predict_proba(X_transformed)[0]
        confidence = float(np.max(probabilities)) * 100
    else:
        # Models without predict_proba (shouldn't happen for the notebook's
        # Random Forest, but kept defensive for any future model swap)
        # can't report a real confidence - 100% would be misleading, so
        # this is flagged rather than guessed.
        confidence = float("nan")

    return str(prediction), round(confidence, 2)


def build_confidence_payload(prediction: str, confidence: float) -> dict:
    """
    Return the exact {"prediction": ..., "confidence": ...} shape from the
    Milestone 3 spec, for callers that just want that piece on its own
    (e.g. a lightweight internal endpoint) rather than the full
    PredictionResponse that inference.py builds.
    """
    return {"prediction": prediction, "confidence": confidence}
