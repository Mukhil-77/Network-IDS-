"""
Confidence calibration for IDS model predictions.

Implements probability calibration (Platt scaling, isotonic regression) to make
model confidence scores reliable for risk scoring and threshold decisions.

Research contribution: Coverage-aware calibrated confidence -> risk score.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from sklearn.calibration import CalibratedClassifierCV
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split

from backend.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class CalibrationResult:
    """Result of calibration process."""
    calibrator: Any
    method: str
    ece_before: float  # Expected Calibration Error before
    ece_after: float   # Expected Calibration Error after
    brier_before: float
    brier_after: float
    reliability_diagram: Dict[str, List[float]]  # bin centers, accuracies, confidences


def expected_calibration_error(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    n_bins: int = 10
) -> float:
    """
    Compute Expected Calibration Error (ECE).
    
    ECE measures the difference between predicted confidence and empirical accuracy.
    Lower is better (perfect calibration = 0).
    """
    confidences = np.max(y_prob, axis=1)
    predictions = np.argmax(y_prob, axis=1)
    accuracies = (predictions == y_true).astype(float)
    
    bin_boundaries = np.linspace(0, 1, n_bins + 1)
    bin_lowers = bin_boundaries[:-1]
    bin_uppers = bin_boundaries[1:]
    
    ece = 0.0
    for bin_lower, bin_upper in zip(bin_lowers, bin_uppers):
        in_bin = (confidences > bin_lower) & (confidences <= bin_upper)
        prop_in_bin = in_bin.mean()
        
        if prop_in_bin > 0:
            accuracy_in_bin = accuracies[in_bin].mean()
            avg_confidence_in_bin = confidences[in_bin].mean()
            ece += np.abs(avg_confidence_in_bin - accuracy_in_bin) * prop_in_bin
    
    return float(ece)


def brier_score(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    """
    Compute Brier score (mean squared error of probability predictions).
    
    Lower is better (perfect = 0).
    """
    n_classes = y_prob.shape[1]
    y_onehot = np.eye(n_classes)[y_true]
    return float(np.mean((y_prob - y_onehot) ** 2))


def compute_reliability_diagram(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    n_bins: int = 10
) -> Dict[str, List[float]]:
    """
    Compute reliability diagram data for visualization.
    
    Returns bin centers, accuracies, confidences, and counts.
    """
    confidences = np.max(y_prob, axis=1)
    predictions = np.argmax(y_prob, axis=1)
    accuracies = (predictions == y_true).astype(float)
    
    bin_boundaries = np.linspace(0, 1, n_bins + 1)
    bin_lowers = bin_boundaries[:-1]
    bin_uppers = bin_boundaries[1:]
    
    bin_centers = []
    bin_accuracies = []
    bin_confidences = []
    bin_counts = []
    
    for bin_lower, bin_upper in zip(bin_lowers, bin_uppers):
        in_bin = (confidences > bin_lower) & (confidences <= bin_upper)
        if in_bin.any():
            bin_centers.append((bin_lower + bin_upper) / 2)
            bin_accuracies.append(float(accuracies[in_bin].mean()))
            bin_confidences.append(float(confidences[in_bin].mean()))
            bin_counts.append(int(in_bin.sum()))
        else:
            bin_centers.append((bin_lower + bin_upper) / 2)
            bin_accuracies.append(0.0)
            bin_confidences.append(0.0)
            bin_counts.append(0)
    
    return {
        "bin_centers": bin_centers,
        "bin_accuracies": bin_accuracies,
        "bin_confidences": bin_confidences,
        "bin_counts": bin_counts,
    }


class ConfidenceCalibrator:
    """
    Handles confidence calibration for IDS classifiers.
    
    Supports multiple calibration methods:
    - Platt scaling (Logistic Regression)
    - Isotonic Regression
    - Temperature scaling (for neural nets)
    """
    
    def __init__(self, method: str = "isotonic", cv: int = 3):
        """
        Initialize calibrator.
        
        Args:
            method: "platt", "isotonic", or "sigmoid" (Platt via LogisticRegression)
            cv: Cross-validation folds for CalibratedClassifierCV
        """
        self.method = method
        self.cv = cv
        self.calibrator = None
        self.is_fitted = False
        self.classes_ = None
        
    def fit(self, model: Any, X_val: np.ndarray, y_val: np.ndarray) -> CalibrationResult:
        """
        Fit calibrator on validation data.
        
        Args:
            model: Fitted classifier with predict_proba method
            X_val: Validation features
            y_val: Validation labels
            
        Returns:
            CalibrationResult with before/after metrics
        """
        # Get uncalibrated probabilities
        y_prob_uncalibrated = model.predict_proba(X_val)
        
        # Compute metrics before calibration
        ece_before = expected_calibration_error(y_val, y_prob_uncalibrated)
        brier_before = brier_score(y_val, y_prob_uncalibrated)
        reliability_before = compute_reliability_diagram(y_val, y_prob_uncalibrated)
        
        # Create calibrator
        if self.method == "platt":
            self.calibrator = CalibratedClassifierCV(
                model, method="sigmoid", cv=self.cv, ensemble=False
            )
        elif self.method == "isotonic":
            self.calibrator = CalibratedClassifierCV(
                model, method="isotonic", cv=self.cv, ensemble=False
            )
        elif self.method == "sigmoid":
            # Explicit Platt scaling via LogisticRegression on logits
            self.calibrator = CalibratedClassifierCV(
                model, method="sigmoid", cv=self.cv, ensemble=False
            )
        else:
            raise ValueError(f"Unknown calibration method: {self.method}")
        
        # Fit calibrator
        self.calibrator.fit(X_val, y_val)
        self.is_fitted = True
        self.classes_ = self.calibrator.classes_
        
        # Get calibrated probabilities
        y_prob_calibrated = self.calibrator.predict_proba(X_val)
        
        # Compute metrics after calibration
        ece_after = expected_calibration_error(y_val, y_prob_calibrated)
        brier_after = brier_score(y_val, y_prob_calibrated)
        reliability_after = compute_reliability_diagram(y_val, y_prob_calibrated)
        
        logger.info(
            f"Calibration ({self.method}): ECE {ece_before:.4f} -> {ece_after:.4f}, "
            f"Brier {brier_before:.4f} -> {brier_after:.4f}"
        )
        
        return CalibrationResult(
            calibrator=self.calibrator,
            method=self.method,
            ece_before=ece_before,
            ece_after=ece_after,
            brier_before=brier_before,
            brier_after=brier_after,
            reliability_diagram=reliability_after,
        )
    
    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Get calibrated probabilities."""
        if not self.is_fitted:
            raise RuntimeError("Calibrator not fitted. Call fit() first.")
        return self.calibrator.predict_proba(X)
    
    def predict(self, X: np.ndarray) -> np.ndarray:
        """Get calibrated predictions."""
        if not self.is_fitted:
            raise RuntimeError("Calibrator not fitted. Call fit() first.")
        return self.calibrator.predict(X)
    
    def save(self, path: Path):
        """Save calibrator to disk."""
        import joblib
        joblib.dump(self.calibrator, path)
        logger.info(f"Saved calibrator to {path}")
    
    @classmethod
    def load(cls, path: Path, method: str = "isotonic") -> "ConfidenceCalibrator":
        """Load calibrator from disk."""
        import joblib
        calibrator = joblib.load(path)
        obj = cls(method=method)
        obj.calibrator = calibrator
        obj.is_fitted = True
        obj.classes_ = calibrator.classes_
        return obj


def calibrate_model(
    model: Any,
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_val: np.ndarray,
    y_val: np.ndarray,
    method: str = "isotonic",
) -> Tuple[Any, CalibrationResult]:
    """
    Convenience function to calibrate a model.
    
    Args:
        model: Unfitted base model
        X_train: Training features
        y_train: Training labels
        X_val: Validation features
        y_val: Validation labels
        method: Calibration method
        
    Returns:
        Tuple of (calibrated model, CalibrationResult)
    """
    # First train base model
    model.fit(X_train, y_train)
    
    # Calibrate on validation set
    calibrator = ConfidenceCalibrator(method=method)
    result = calibrator.fit(model, X_val, y_val)
    
    return calibrator, result


def compute_ece_per_class(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    n_bins: int = 10
) -> Dict[int, float]:
    """Compute ECE for each class separately (one-vs-rest)."""
    n_classes = y_prob.shape[1]
    ece_per_class = {}
    
    for class_idx in range(n_classes):
        y_true_binary = (y_true == class_idx).astype(int)
        y_prob_binary = y_prob[:, class_idx]
        
        # For binary case, compute ECE on positive class probability
        confidences = y_prob_binary
        accuracies = (y_true == class_idx).astype(float)
        
        bin_boundaries = np.linspace(0, 1, n_bins + 1)
        bin_lowers = bin_boundaries[:-1]
        bin_uppers = bin_boundaries[1:]
        
        ece = 0.0
        for bin_lower, bin_upper in zip(bin_lowers, bin_uppers):
            in_bin = (confidences > bin_lower) & (confidences <= bin_upper)
            prop_in_bin = in_bin.mean()
            
            if prop_in_bin > 0:
                accuracy_in_bin = accuracies[in_bin].mean()
                avg_confidence_in_bin = confidences[in_bin].mean()
                ece += np.abs(avg_confidence_in_bin - accuracy_in_bin) * prop_in_bin
        
        ece_per_class[class_idx] = float(ece)
    
    return ece_per_class


# Example usage:
#
# from backend.ml.calibration import calibrate_model, ConfidenceCalibrator
# from sklearn.ensemble import RandomForestClassifier
# from sklearn.model_selection import train_test_split
#
# # Split data: train / val / test
# X_train, X_temp, y_train, y_temp = train_test_split(X, y, test_size=0.3, random_state=42)
# X_val, X_test, y_val, y_test = train_test_split(X_temp, y_temp, test_size=0.5, random_state=42)
#
# # Train base model
# model = RandomForestClassifier(n_estimators=100, random_state=42)
#
# # Calibrate
# calibrator, result = calibrate_model(
#     RandomForestClassifier(n_estimators=100, random_state=42),
#     X_train, y_train, X_val, y_val, method="isotonic"
# )
#
# # Use calibrated probabilities
# y_prob_calibrated = calibrator.predict_proba(X_test)
# print(f"ECE before: {result.ece_before:.4f}, after: {result.ece_after:.4f}")