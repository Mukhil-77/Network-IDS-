"""
Zero-day / Unseen Attack Detection using Isolation Forest.

Trains an Isolation Forest on benign traffic only to detect anomalous flows
that don't match known attack patterns or normal behavior.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split

from backend.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class AnomalyDetectionResult:
    """Result of anomaly detection for a single flow or batch."""
    is_anomaly: bool
    anomaly_score: float  # Higher = more anomalous (0-1 scale)
    threshold: float
    features_contributing: List[str] = None
    confidence: float = 0.0


@dataclass
class ZeroDayDetectionResult:
    """Result of zero-day detection combining supervised + anomaly."""
    predicted_class: str
    confidence: float
    is_known_attack: bool
    is_anomaly: bool
    anomaly_score: float
    is_zero_day: bool
    zero_day_confidence: float
    reasoning: List[str]
    recommended_action: str = ""


class IsolationForestDetector:
    """
    Isolation Forest detector trained on benign traffic only.

    Used to detect anomalous flows that may represent zero-day attacks
    or novel attack patterns not seen during training.
    """

    def __init__(
        self,
        n_estimators: int = 200,
        max_samples: Union[int, float] = "auto",
        contamination: float = 0.01,
        max_features: float = 1.0,
        random_state: int = 42,
        n_jobs: int = -1,
    ):
        """
        Initialize Isolation Forest detector.

        Args:
            n_estimators: Number of trees in the forest
            max_samples: Number of samples to draw for each tree
            contamination: Expected proportion of anomalies (used for threshold)
            max_features: Number of features to draw for each tree
            random_state: Random seed
            n_jobs: Number of parallel jobs
        """
        self.n_estimators = n_estimators
        self.max_samples = max_samples
        self.contamination = contamination
        self.max_features = max_features
        self.random_state = random_state
        self.n_jobs = n_jobs

        self.isolation_forest = IsolationForest(
            n_estimators=n_estimators,
            max_samples=max_samples,
            contamination=contamination,
            max_features=max_features,
            random_state=random_state,
            n_jobs=n_jobs,
        )
        self.scaler = StandardScaler()
        self.is_fitted = False
        self.feature_names = None
        self.threshold = None

    def fit(self, X_benign: np.ndarray, feature_names: Optional[List[str]] = None) -> "IsolationForestDetector":
        """
        Fit the Isolation Forest on benign traffic only.

        Args:
            X_benign: Benign traffic features (n_samples, n_features)
            feature_names: Optional feature names for interpretation

        Returns:
            Self for chaining
        """
        logger.info(f"Fitting Isolation Forest on {len(X_benign)} benign samples")

        # Scale features
        X_scaled = self.scaler.fit_transform(X_benign)

        # Fit Isolation Forest
        self.isolation_forest.fit(X_scaled)
        self.is_fitted = True
        self.feature_names = feature_names or [f"feature_{i}" for i in range(X_benign.shape[1])]

        # Determine threshold from training data
        scores = self.isolation_forest.decision_function(self.scaler.transform(X_benign))
        # Lower decision_function = more anomalous
        # Set threshold at contamination percentile
        self.threshold = np.percentile(scores, self.contamination * 100)

        logger.info(f"Isolation Forest fitted. Threshold: {self.threshold:.4f}")
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        """
        Predict anomaly labels (1 = normal, -1 = anomaly).

        Args:
            X: Input features (n_samples, n_features)

        Returns:
            Array of 1 (normal) or -1 (anomaly)
        """
        if not self.is_fitted:
            raise RuntimeError("Detector not fitted. Call fit() first.")

        X_scaled = self.scaler.transform(X)
        return self.isolation_forest.predict(X_scaled)

    def decision_function(self, X: np.ndarray) -> np.ndarray:
        """
        Get anomaly scores (lower = more anomalous).

        Args:
            X: Input features (n_samples, n_features)

        Returns:
            Anomaly scores (lower = more anomalous)
        """
        if not self.is_fitted:
            raise RuntimeError("Detector not fitted. Call fit() first.")

        X_scaled = self.scaler.transform(X)
        return self.isolation_forest.decision_function(X_scaled)

    def anomaly_score(self, X: np.ndarray) -> np.ndarray:
        """
        Get normalized anomaly scores (0-1, higher = more anomalous).

        Args:
            X: Input features (n_samples, n_features)

        Returns:
            Normalized anomaly scores (0-1, higher = more anomalous)
        """
        scores = self.decision_function(X)
        # Normalize: lower decision_function = more anomalous
        # Invert and normalize to 0-1
        normalized = 1 - (scores - scores.min()) / (scores.max() - scores.min() + 1e-10)
        return normalized

    def detect(self, X: np.ndarray, threshold: Optional[float] = None) -> List[AnomalyDetectionResult]:
        """
        Detect anomalies in input data.

        Args:
            X: Input features (n_samples, n_features)
            threshold: Custom threshold (uses fitted threshold if None)

        Returns:
            List of AnomalyDetectionResult
        """
        if not self.is_fitted:
            raise RuntimeError("Detector not fitted. Call fit() first.")

        threshold = threshold or self.threshold
        scores = self.decision_function(X)
        is_anomaly = scores < threshold
        anomaly_scores = self.anomaly_score(X)

        results = []
        for i in range(len(X)):
            results.append(AnomalyDetectionResult(
                is_anomaly=bool(is_anomaly[i]),
                anomaly_score=float(anomaly_scores[i]),
                threshold=float(threshold),
            ))

        return results

    def get_feature_contributions(self, X: np.ndarray, top_k: int = 10) -> List[List[Tuple[str, float]]]:
        """
        Get approximate feature contributions for anomaly detection.

        Uses a simplified approach: for each anomalous sample, compute
        which features deviate most from benign mean.

        Args:
            X: Input features (n_samples, n_features)
            top_k: Number of top contributing features to return

        Returns:
            List of (feature_name, contribution) for each sample
        """
        if not self.is_fitted:
            raise RuntimeError("Detector not fitted. Call fit() first.")

        X_scaled = self.scaler.transform(X)
        benign_mean = self.scaler.mean_

        results = []
        for i in range(len(X)):
            deviations = np.abs(X_scaled[i] - benign_mean)
            top_indices = np.argsort(deviations)[-top_k:][::-1]

            contributions = []
            for idx in top_indices:
                feature_name = self.feature_names[idx] if self.feature_names else f"feature_{idx}"
                contribution = float(deviations[idx])
                contributions.append((feature_name, contribution))

            results.append(contributions)

        return results

    def save(self, path: Union[str, Path]) -> None:
        """Save detector to disk."""
        import joblib
        joblib.dump({
            'isolation_forest': self.isolation_forest,
            'scaler': self.scaler,
            'threshold': self.threshold,
            'feature_names': self.feature_names,
            'is_fitted': self.is_fitted,
            'n_estimators': self.n_estimators,
            'max_samples': self.max_samples,
            'contamination': self.contamination,
            'max_features': self.max_features,
            'random_state': self.random_state,
            'n_jobs': self.n_jobs,
        }, path)
        logger.info(f"Saved Isolation Forest detector to {path}")

    @classmethod
    def load(cls, path: Union[str, Path]) -> "IsolationForestDetector":
        """Load detector from disk."""
        import joblib
        data = joblib.load(path)

        detector = cls(
            n_estimators=data['n_estimators'],
            max_samples=data['max_samples'],
            contamination=data['contamination'],
            max_features=data['max_features'],
            random_state=data['random_state'],
            n_jobs=data['n_jobs'],
        )
        detector.isolation_forest = data['isolation_forest']
        detector.scaler = data['scaler']
        detector.threshold = data['threshold']
        detector.feature_names = data['feature_names']
        detector.is_fitted = data['is_fitted']

        logger.info(f"Loaded Isolation Forest detector from {path}")
        return detector


@dataclass
class ZeroDayDetectionResult:
    """Result of zero-day detection combining supervised + anomaly."""
    predicted_class: str
    confidence: float
    is_known_attack: bool
    is_anomaly: bool
    anomaly_score: float
    is_zero_day: bool
    zero_day_confidence: float
    reasoning: List[str]
    recommended_action: str = ""


class ZeroDayDetector:
    """
    Combined zero-day detection using supervised classifier + anomaly detection.

    Combines:
    1. Supervised classifier (e.g., Random Forest) for known attacks
    2. Isolation Forest on benign traffic for unknown/anomalous detection

    Produces a unified detection result with:
    - Known attack classification
    - Anomaly detection for unknown/zero-day
    - Combined confidence and reasoning
    
    Decision Rule:
    - t_conf: Supervised confidence threshold (calibrated for 1% FPR on benign)
    - t_anom: Anomaly score threshold (calibrated for 1% FPR on benign)
    - Flow is "possible zero-day" if:
        (supervised_conf < t_conf AND anomaly_score > t_anom) OR
        (anomaly_score > t_anom AND supervised_conf < t_conf)
    """

    def __init__(
        self,
        supervised_model: Any,
        anomaly_detector: IsolationForestDetector,
        t_conf: float = 0.5,       # Supervised confidence threshold
        t_anom: float = 0.5,       # Anomaly score threshold
        unknown_threshold: float = 0.5,      # Legacy alias for t_anom
        low_confidence_threshold: float = 0.5,  # Legacy alias for t_conf
    ):
        """
        Initialize zero-day detector.

        Args:
            supervised_model: Fitted supervised classifier (e.g., Random Forest)
            anomaly_detector: Fitted IsolationForestDetector
            t_conf: Supervised confidence threshold (calibrated for 1% FPR on benign)
            t_anom: Anomaly score threshold (calibrated for 1% FPR on benign)
            unknown_threshold: Legacy alias for t_anom
            low_confidence_threshold: Legacy alias for t_conf
        """
        self.supervised_model = supervised_model
        self.anomaly_detector = anomaly_detector
        self.t_conf = t_conf
        self.t_anom = t_anom
        self.unknown_threshold = unknown_threshold  # Legacy
        self.low_confidence_threshold = low_confidence_threshold  # Legacy
        self.is_fitted = False

    def fit(self, X_benign: np.ndarray, y_benign: np.ndarray,
            target_fpr: float = 0.01) -> Tuple[float, float]:
        """
        Calibrate t_conf and t_anom thresholds to achieve target FPR on benign traffic.

        Args:
            X_benign: Benign traffic features
            y_benign: Benign labels (all "BENIGN")
            target_fpr: Target false positive rate (default 1%)

        Returns:
            (t_conf, t_anom) calibrated thresholds
        """

        logger.info(f"Calibrating thresholds for {target_fpr*100:.1f}% target FPR on benign traffic")

        # Get supervised predictions on benign data
        supervised_proba = self.supervised_model.predict_proba(X_benign)
        supervised_conf = np.max(supervised_proba, axis=1)
        supervised_pred = self.supervised_model.predict(X_benign)

        # Get anomaly detection
        anomaly_results = self.anomaly_detector.detect(X_benign)
        anomaly_scores = [r.anomaly_score for r in anomaly_results]

        # Find t_conf: supervised confidence threshold for target FPR
        sorted_conf = np.sort(supervised_conf)
        n_benign = len(supervised_conf)
        n_fp_allowed = int(np.ceil(target_fpr * n_benign))
        if n_fp_allowed > 0:
            t_conf = sorted_conf[-n_fp_allowed]  # Threshold above which we have <= target_fpr FPR
        else:
            t_conf = 0.0

        # Find t_anom: anomaly score threshold for target FPR
        sorted_anom = np.sort(anomaly_scores)
        n_fp_anom = int(np.ceil(target_fpr * n_benign))
        if n_fp_anom > 0:
            t_anom = sorted_anom[-n_fp_anom]
        else:
            t_anom = 0.0

        # Ensure minimum reasonable thresholds
        self.t_conf = max(self.t_conf, t_conf)
        self.t_anom = max(self.t_anom, t_anom)

        # Validate on benign data
        benign_fpr_conf = (supervised_conf < self.t_conf).mean()
        benign_fpr_anom = (np.array(anomaly_scores) > self.t_anom).mean()

        logger.info(f"Calibrated thresholds: t_conf={self.t_conf:.4f}, t_anom={self.t_anom:.4f}")
        logger.info(f"Benign FPR (conf): {benign_fpr_conf:.4f}, Benign FPR (anom): {benign_fpr_anom:.4f}")

        self.is_fitted = True
        return self.t_conf, self.t_anom

    def predict(self, X: np.ndarray, feature_names: Optional[List[str]] = None) -> List[ZeroDayDetectionResult]:
        """
        Predict with combined zero-day detection.

        Args:
            X: Input features (n_samples, n_features)
            feature_names: Optional feature names for interpretation

        Returns:
            List of ZeroDayDetectionResult
        """
        if not self.is_fitted:
            raise RuntimeError("ZeroDayDetector not fitted. Call calibrate_thresholds() first.")

        # Get supervised predictions
        supervised_pred = self.supervised_model.predict(X)
        supervised_proba = self.supervised_model.predict_proba(X) if hasattr(self.supervised_model, "predict_proba") else None

        # Get anomaly detection
        anomaly_results = self.anomaly_detector.detect(X)
        anomaly_scores = [r.anomaly_score for r in anomaly_results]
        is_anomaly = [r.is_anomaly for r in anomaly_results]

        results = []
        for i in range(len(X)):
            pred_class = supervised_pred[i]
            confidence = float(np.max(supervised_proba[i])) if supervised_proba is not None else 1.0
            anomaly_score = anomaly_scores[i]
            is_anom = is_anomaly[i]

            # Determine if zero-day using new decision rule with t_conf and t_anom
            is_known_attack = pred_class != "BENIGN"

            # New decision rule:
            # Flow is "possible zero-day" if:
            # (supervised_conf < t_conf AND anomaly_score > t_anom) OR
            # (anomaly_score > t_anom AND supervised_conf < t_conf)
            supervised_conf = float(np.max(supervised_proba[i])) if supervised_proba is not None else 1.0
            anomaly_score = anomaly_scores[i]

            # New decision rule:
            # Flow is "possible zero-day" if:
            # (supervised_conf < t_conf AND anomaly_score > t_anom) OR
            # (anomaly_score > t_anom AND supervised_conf < t_conf)
            is_zero_day = (
                (supervised_conf < self.t_conf and anomaly_score > self.t_anom) or
                (anomaly_score > self.t_anom and supervised_conf < self.t_conf)
            )

            is_known_attack = pred_class != "BENIGN"

            # Zero-day confidence
            zero_day_confidence = 0.0
            if is_anom:
                zero_day_confidence = anomaly_score

            # Combined reasoning
            reasoning = []
            if is_known_attack:
                reasoning.append(f"Classified as {pred_class} by supervised model (confidence: {confidence:.1%})")
            else:
                reasoning.append("Classified as BENIGN by supervised model")

            if is_anom:
                reasoning.append(f"Anomaly detected (score: {anomaly_score:.3f})")
                if is_known_attack:
                    reasoning.append("Known attack type but anomalous behavior")
                else:
                    reasoning.append("Possible zero-day / unknown attack")
            else:
                reasoning.append("No anomaly detected")

            results.append(ZeroDayDetectionResult(
                predicted_class=pred_class,
                confidence=confidence,
                is_known_attack=is_known_attack,
                is_anomaly=is_anom,
                anomaly_score=float(anomaly_score),
                is_zero_day=is_zero_day,
                zero_day_confidence=zero_day_confidence,
                reasoning=reasoning,
                recommended_action=self._get_recommended_action(is_zero_day, is_known_attack, anomaly_score),
            ))

        return results

    def _get_recommended_action(self, is_zero_day: bool, is_known_attack: bool, anomaly_score: float) -> str:
        """Get recommended action based on detection result."""
        if is_zero_day:
            return "Immediate containment: isolate source, block IP, escalate to IR team"
        elif is_known_attack:
            return "Alert analyst: investigate known attack pattern"
        else:
            return "Log and monitor: no immediate action required"

    def compare_detection_methods(self, X: np.ndarray, y_true: np.ndarray) -> Dict[str, Any]:
        """
        Compare three detection methods on labeled data.

        Args:
            X: Input features (n_samples, n_features)
            y_true: True labels (BENIGN or attack class names)

        Returns:
            Dictionary with comparison metrics for three methods:
            - "confidence_only": supervised confidence threshold only
            - "anomaly_only": Isolation Forest only
            - "combined": combined decision rule (t_conf + t_anom)
        """
        if not self.is_fitted:
            raise RuntimeError("ZeroDayDetector not fitted. Call calibrate_thresholds() first.")

        # Get predictions from all three methods
        supervised_pred = self.supervised_model.predict(X)
        supervised_proba = self.supervised_model.predict_proba(X) if hasattr(self.supervised_model, "predict_proba") else None
        supervised_conf = np.max(self.supervised_model.predict_proba(X), axis=1) if hasattr(self.supervised_model, "predict_proba") else np.ones(len(X))

        anomaly_results = self.anomaly_detector.detect(X)
        anomaly_scores = [r.anomaly_score for r in anomaly_results]
        is_anomaly = [r.is_anomaly for r in anomaly_results]

        results = {
            "confidence_only": {"y_pred": [], "y_true": []},
            "anomaly_only": {"y_pred": [], "y_true": []},
            "combined": {"y_pred": [], "y_true": []}
        }

        # Ground truth: BENIGN vs ATTACK
        y_true_binary = (y_true != "BENIGN").astype(int)

        for i in range(len(X)):
            supervised_conf = float(np.max(self.supervised_model.predict_proba(X[i:i+1])[0])) if hasattr(self.supervised_model, "predict_proba") else 1.0
            supervised_pred = self.supervised_model.predict(X[i:i+1])[0]
            anomaly_score = anomaly_scores[i]
            is_anom = is_anomaly[i]

            # Method 1: Confidence threshold only
            conf_pred = 1 if supervised_conf < self.t_conf else 0
            results["confidence_only"]["y_pred"].append(conf_pred)
            results["confidence_only"]["y_true"].append(1 if y_true[i] != "BENIGN" else 0)

            # Method 2: Anomaly threshold only
            anom_pred = 1 if anomaly_score > self.t_anom else 0
            results["anomaly_only"]["y_pred"].append(anom_pred)
            results["anomaly_only"]["y_true"].append(1 if y_true[i] != "BENIGN" else 0)

            # Method 3: Combined
            is_zero_day = (
                (supervised_conf < self.t_conf and anomaly_score > self.t_anom) or
                (anomaly_score > self.t_anom and supervised_conf < self.t_conf)
            )
            combined_pred = 1 if is_zero_day else 0
            results["combined"]["y_pred"].append(combined_pred)
            results["combined"]["y_true"].append(1 if y_true[i] != "BENIGN" else 0)

        # Compute metrics for each method
        from sklearn.metrics import precision_score, recall_score, f1_score, confusion_matrix

        results_dict = {}
        for method_name, method_results in results.items():
            y_pred = method_results["y_pred"]
            y_true = method_results["y_true"]

            if len(y_pred) > 0:
                tn, fp, fn, tp = confusion_matrix(y_true, y_pred).ravel()
                precision = precision_score(y_true, y_pred, zero_division=0)
                recall = recall_score(y_true, y_pred, zero_division=0)
                f1 = f1_score(y_true, y_pred, zero_division=0)
                fpr = fp / (fp + tn) if (fp + tn) > 0 else 0
                fnr = fn / (fn + tp) if (fn + tp) > 0 else 0

                results_dict[method_name] = {
                    "precision": precision,
                    "recall": recall,
                    "f1": f1,
                    "fpr": fpr,
                    "fnr": fnr,
                    "tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)
                }

        return results_dict

    def _get_recommended_action(self, is_zero_day: bool, is_known_attack: bool, anomaly_score: float) -> str:
        """Get recommended action based on detection result."""
        if is_zero_day:
            return "Immediate containment: isolate source, block IP, escalate to IR team"
        elif is_known_attack:
            return "Alert analyst: investigate known attack pattern"
        else:
            return "Log and monitor: no immediate action required"

    def save(self, path: Union[str, Path]) -> None:
        """Save both models."""
        import joblib
        joblib.dump({
            'supervised_model': self.supervised_model,
            'anomaly_detector': self.anomaly_detector,
            'unknown_threshold': self.unknown_threshold,
            'low_confidence_threshold': self.low_confidence_threshold,
        }, path)
        logger.info(f"Saved ZeroDayDetector to {path}")

    @classmethod
    def load(cls, path: Union[str, Path]) -> "ZeroDayDetector":
        """Load ZeroDayDetector from disk."""
        import joblib
        data = joblib.load(path)

        detector = cls(
            supervised_model=data['supervised_model'],
            anomaly_detector=data['anomaly_detector'],
            unknown_threshold=data['unknown_threshold'],
            low_confidence_threshold=data['low_confidence_threshold'],
        )
        logger.info(f"Loaded ZeroDayDetector from {path}")
        return detector


def train_anomaly_detector(
    X_benign: np.ndarray,
    feature_names: Optional[List[str]] = None,
    contamination: float = 0.01,
    n_estimators: int = 200,
) -> IsolationForestDetector:
    """
    Convenience function to train an Isolation Forest on benign traffic.

    Args:
        X_benign: Benign traffic features
        feature_names: Optional feature names
        contamination: Expected anomaly proportion
        n_estimators: Number of trees

    Returns:
        Fitted IsolationForestDetector
    """
    detector = IsolationForestDetector(
        n_estimators=n_estimators,
        contamination=contamination,
        random_state=42,
    )
    detector.fit(X_benign, feature_names)
    return detector


def create_zero_day_detector(
    supervised_model: Any,
    X_benign: np.ndarray,
    feature_names: Optional[List[str]] = None,
    contamination: float = 0.01,
    unknown_threshold: float = 0.5,
) -> ZeroDayDetector:
    """
    Create a complete ZeroDayDetector with supervised model and anomaly detector.

    Args:
        supervised_model: Fitted supervised classifier
        X_benign: Benign training data for anomaly detector
        feature_names: Feature names
        contamination: Contamination parameter for Isolation Forest
        unknown_threshold: Threshold for unknown classification

    Returns:
        Configured ZeroDayDetector
    """
    anomaly_detector = train_anomaly_detector(X_benign, feature_names, contamination=contamination)
    return ZeroDayDetector(
        supervised_model=supervised_model,
        anomaly_detector=anomaly_detector,
        unknown_threshold=unknown_threshold,
    )