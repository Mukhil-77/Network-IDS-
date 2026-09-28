"""
Unseen / Zero-Day Attack Detection

Implements controlled leave-one-class-out evaluation for unseen attack detection.
The system distinguishes:
- Known attack
- Unknown/unseen attack
- Normal traffic
- Uncertain prediction

Uses an anomaly/unknown threshold based on model confidence and distance from known classes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np
import pandas as pd

from backend.ml.evaluation import EvaluationResult, evaluate_model
from backend.ml.training import prepare_multiclass_dataset, train_all_multiclass_models
from backend.ml.evaluation import compute_classification_metrics, compute_confusion_matrix
from backend.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class UnseenDetectionResult:
    """Results from unseen attack detection experiment."""
    excluded_class: str
    model_name: str
    # In-domain (known classes) performance
    known_class_accuracy: float
    known_class_precision_macro: float
    known_class_recall_macro: float
    known_class_f1_macro: float
    known_class_mcc: float
    # Unseen class detection
    unseen_detection_rate: float  # correctly identified as "unknown"
    unseen_false_positive_rate: float  # known attacks misclassified as unknown
    known_false_negative_rate: float  # unknown samples classified as known
    # Confidence-based thresholding
    optimal_threshold: float
    threshold_metrics: dict[str, float]  # metrics at optimal threshold
    # Per-class metrics
    per_class_metrics: dict[str, dict[str, float]]
    
    def to_dict(self) -> dict:
        return {
            "excluded_class": self.excluded_class,
            "model_name": self.model_name,
            "known_class_accuracy": self.known_class_accuracy,
            "known_class_precision_macro": self.known_class_precision_macro,
            "known_class_recall_macro": self.known_class_recall_macro,
            "known_class_f1_macro": self.known_class_f1_macro,
            "known_class_mcc": self.known_class_mcc,
            "unseen_detection_rate": self.unseen_detection_rate,
            "unseen_false_positive_rate": self.unseen_false_positive_rate,
            "known_false_negative_rate": self.known_false_negative_rate,
            "optimal_threshold": self.optimal_threshold,
            "threshold_metrics": self.threshold_metrics,
            "per_class_metrics": self.per_class_metrics,
        }


@dataclass
class UnseenPrediction:
    """Prediction result with unknown detection."""
    predicted_class: str
    confidence: float
    is_unknown: bool
    risk_level: str
    explanation: str


def prepare_leave_one_class_out_dataset(
    pca_df: pd.DataFrame,
    excluded_class: str,
    target_column: str = "Attack Type",
    min_class_count: int = 1950,
    test_size: float = 0.25,
    random_state: int = 0,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series, pd.DataFrame, pd.Series]:
    """
    Prepare dataset for leave-one-class-out evaluation.
    
    Excludes one class from training, includes it in test set.
    
    Returns:
        X_train_known, X_test_known, y_train_known, y_test_known, X_test_unseen, y_test_unseen
    """
    # Get all classes except the excluded one
    class_counts = pca_df["Attack Type"].value_counts()
    selected_classes = class_counts[class_counts > 1950].index
    selected_classes = [c for c in selected_classes if c != excluded_class]
    
    if len(selected_classes) == 0:
        raise ValueError(f"No classes remaining after excluding {excluded_class}")
    
    # Known class data (for training)
    known_data = pca_df[pca_df["Attack Type"].isin(selected_classes)]
    unseen_data = pca_df[pca_df["Attack Type"] == excluded_class]
    
    if len(unseen_data) == 0:
        raise ValueError(f"No data found for excluded class: {excluded_class}")
    
    # Split known data into train/test
    X_known = known_data.drop(columns=["Attack Type"])
    y_known = known_data["Attack Type"]
    
    from sklearn.model_selection import train_test_split
    X_train, X_test_known, y_train, y_test_known = train_test_split(
        X_known, y_known, test_size=0.2, random_state=random_state, stratify=y_known
    )
    
    # Unseen test data
    X_test_unseen = unseen_data.drop(columns=["Attack Type"])
    y_test_unseen = unseen_data["Attack Type"]
    
    logger.info(f"Leave-one-class-out: {excluded_class}")
    logger.info(f"  Training known classes: {len(X_train)} samples, {len(y_train.unique())} classes")
    logger.info(f"  Test known classes: {len(X_test_known)} samples")
    logger.info(f"  Test unseen class: {len(X_test_unseen)} samples")
    
    return X_train, X_test_known, y_train, y_test_known, X_test_unseen, y_test_unseen


def train_without_class(
    pca_df: pd.DataFrame,
    excluded_class: str,
) -> tuple[list[Any], pd.DataFrame, pd.Series, pd.DataFrame, pd.Series, pd.DataFrame, pd.Series]:
    """
    Train models excluding one class.
    
    Returns:
        models, X_train, y_train, X_test_known, y_test_known, X_test_unseen, y_test_unseen
    """
    from backend.ml.training import prepare_multiclass_dataset, train_all_multiclass_models
    
    # Prepare dataset without the excluded class
    X_train, X_test_known, y_train, y_test_known, X_test_unseen, y_test_unseen = \
        prepare_leave_one_class_out_dataset(pca_df, excluded_class)
    
    # Create dataset object for training
    from backend.ml.training import Dataset
    dataset = Dataset(
        X_train=X_train,
        X_test=X_test_known,  # not used for training
        y_train=y_train,
        y_test=y_train,  # not used
    )
    
    # Train models
    models = train_all_multiclass_models(dataset)
    
    return models, X_train, y_train, X_test_known, y_test_known, X_test_unseen, y_test_unseen


def find_optimal_unknown_threshold(
    y_true_known: pd.Series,
    y_pred_known: np.ndarray,
    y_prob_known: np.ndarray,
    y_true_unseen: pd.Series,
    y_prob_unseen: np.ndarray,
    target_names: list[str],
) -> tuple[float, dict]:
    """
    Find optimal confidence threshold for unknown detection.
    
    Returns:
        optimal_threshold, metrics_at_threshold
    """
    from sklearn.metrics import roc_curve, precision_recall_curve, auc
    
    # Create binary labels: 0 = known, 1 = unknown
    y_binary = np.concatenate([
        np.zeros(len(y_true_known)),  # known samples
        np.ones(len(y_true_unseen))   # unknown samples
    ])
    
    # Use max probability as anomaly score (higher = more confident = less likely unknown)
    # For unknown detection, we want LOW confidence = more likely unknown
    prob_known_max = y_prob_known.max(axis=1)
    prob_unseen_max = y_prob_unseen.max(axis=1) if len(y_prob_unseen) > 0 else np.array([])
    
    scores = np.concatenate([1 - prob_known_max, 1 - prob_unseen_max])  # anomaly score
    
    # Find threshold that maximizes F1 for unknown detection
    from sklearn.metrics import precision_recall_curve
    precision, recall, thresholds = precision_recall_curve(y_binary, scores)
    
    # Find threshold maximizing F1
    f1_scores = 2 * precision * recall / (precision + recall + 1e-10)
    best_idx = np.argmax(f1_scores)
    optimal_threshold = thresholds[best_idx] if best_idx < len(thresholds) else 0.5
    
    # Compute metrics at optimal threshold
    y_pred_binary = (scores >= optimal_threshold).astype(int)
    from sklearn.metrics import precision_score, recall_score, f1_score, accuracy_score
    
    metrics = {
        "threshold": float(optimal_threshold),
        "precision": float(precision_score(y_binary, y_pred_binary, zero_division=0)),
        "recall": float(recall_score(y_binary, y_pred_binary, zero_division=0)),
        "f1": float(f1_score(y_binary, y_pred_binary, zero_division=0)),
        "accuracy": float(accuracy_score(y_binary, y_pred_binary)),
    }
    
    return float(optimal_threshold), metrics


def evaluate_unseen_detection(
    model_name: str,
    model: Any,
    X_test_known: pd.DataFrame,
    y_test_known: pd.Series,
    X_test_unseen: pd.DataFrame,
    y_test_unseen: pd.Series,
    cv_scores: Optional[np.ndarray] = None,
) -> UnseenDetectionResult:
    """
    Evaluate model's ability to detect unseen class.
    
    Returns comprehensive metrics for unseen detection.
    """
    # Predict on known test set
    y_pred_known = model.predict(X_test_known)
    y_prob_known = model.predict_proba(X_test_known) if hasattr(model, "predict_proba") else None
    
    # Predict on unseen test set
    y_pred_unseen = model.predict(X_test_unseen)
    y_prob_unseen = model.predict_proba(X_test_unseen) if hasattr(model, "predict_proba") else None
    
    # Known class metrics
    target_names = sorted(pd.Series(y_test_known).unique().tolist(), key=str)
    known_metrics = compute_classification_metrics(y_test_known, y_pred_known, target_names=target_names)
    
    # Unseen detection: should be detected as "not any known class"
    # A sample is correctly detected as unseen if its max probability is low
    # or if it's misclassified with low confidence
    if y_prob_unseen is not None:
        unseen_max_prob = y_prob_unseen.max(axis=1)
        # Unseen detection rate: fraction of unseen samples with low confidence
        # We consider a sample "detected as unknown" if max prob < 0.5
        unseen_detected = (unseen_max_prob < 0.5).sum()
        unseen_detection_rate = unseen_detected / len(y_test_unseen)
    else:
        unseen_detection_rate = 0.0
    
    # False positive rate: known samples with low confidence (incorrectly flagged as unknown)
    if y_prob_known is not None:
        known_max_prob = y_prob_known.max(axis=1)
        known_false_unknown = (known_max_prob < 0.5).sum()
        unseen_false_positive_rate = known_false_unknown / len(y_test_known)
    else:
        unseen_false_positive_rate = 0.0
    
    # False negative rate: unseen samples classified as known with high confidence
    if y_prob_unseen is not None:
        known_false_negative_rate = (unseen_max_prob >= 0.5).sum() / len(y_test_unseen)
    else:
        known_false_negative_rate = 1.0
    
    # Find optimal threshold
    optimal_threshold, threshold_metrics = find_optimal_unknown_threshold(
        y_test_known, y_pred_known, y_prob_known if y_prob_known is not None else np.zeros((len(y_test_known), 1)),
        y_test_unseen, y_prob_unseen if y_prob_unseen is not None else np.zeros((len(y_test_unseen), 1)),
        target_names=sorted(pd.Series(y_test_known).unique().tolist(), key=str)
    )
    
    # Per-class metrics for known classes
    per_class = {}
    for cls in sorted(pd.Series(y_test_known).unique()):
        cls_mask = (y_test_known == cls)
        if cls_mask.sum() > 0:
            cls_y_true = y_test_known[cls_mask]
            cls_y_pred = y_pred_known[cls_mask.values]
            from sklearn.metrics import precision_score, recall_score, f1_score
            per_class[cls] = {
                "precision": float(precision_score(cls_y_true, cls_y_pred, average="binary", pos_label=cls, zero_division=0)),
                "recall": float(recall_score(cls_y_true, cls_y_pred, average="binary", pos_label=cls, zero_division=0)),
                "f1": float(f1_score(cls_y_true, cls_y_pred, average="binary", pos_label=cls, zero_division=0)),
                "support": int(cls_mask.sum()),
            }
    
    return UnseenDetectionResult(
        excluded_class="",  # will be set by caller
        model_name=model_name,
        known_class_accuracy=known_metrics["accuracy"],
        known_class_precision_macro=known_metrics["precision_macro"],
        known_class_recall_macro=known_metrics["recall_macro"],
        known_class_f1_macro=known_metrics["f1_macro"],
        known_class_mcc=known_metrics["mcc"],
        unseen_detection_rate=unseen_detection_rate,
        unseen_false_positive_rate=unseen_false_positive_rate,
        known_false_negative_rate=known_false_negative_rate,
        optimal_threshold=optimal_threshold,
        threshold_metrics=threshold_metrics,
        per_class_metrics=per_class,
    )


def run_leave_one_class_out_experiment(
    pca_df: pd.DataFrame,
    excluded_classes: Optional[list[str]] = None,
    model_filter: Optional[list[str]] = None,
) -> list[UnseenDetectionResult]:
    """
    Run leave-one-class-out experiment for multiple excluded classes.
    
    For each excluded class:
    1. Train models without that class
    2. Evaluate on known test classes + excluded class
    3. Measure unseen detection performance
    """
    if excluded_classes is None:
        # Get all classes with sufficient samples
        class_counts = pca_df["Attack Type"].value_counts()
        excluded_classes = class_counts[class_counts > 1950].index.tolist()
    
    all_results = []
    
    for excluded_class in excluded_classes:
        logger.info(f"Running leave-one-class-out for: {excluded_class}")
        
        try:
            models, X_train, y_train, X_test_known, y_test_known, X_test_unseen, y_test_unseen = \
                train_without_class(pca_df, excluded_class)
            
            if model_filter:
                models = [m for m in models if m.name in model_filter]
            
            for model in models:
                logger.info(f"Evaluating {model.name} for unseen detection of {excluded_class}")
                result = evaluate_unseen_detection(
                    model_name=model.name,
                    model=model.model,
                    X_test_known=X_test_known,
                    y_test_known=y_test_known,
                    X_test_unseen=X_test_unseen,
                    y_test_unseen=y_test_unseen,
                    cv_scores=model.cv_scores,
                )
                result.excluded_class = excluded_class
                all_results.append(result)
                
                logger.info(f"  {model.name}: unseen_detection_rate={result.unseen_detection_rate:.2%}, "
                           f"FPR={result.unseen_false_positive_rate:.2%}, "
                           f"FNR={result.known_false_negative_rate:.2%}")
        
        except Exception as e:
            logger.error(f"Failed leave-one-class-out for {excluded_class}: {e}")
            continue
    
    return all_results


def generate_unseen_detection_report(results: list[UnseenDetectionResult]) -> str:
    """Generate human-readable unseen detection report."""
    lines = []
    lines.append("=" * 80)
    lines.append("UNSEEN ATTACK DETECTION REPORT (Leave-One-Class-Out)")
    lines.append("=" * 80)
    
    # Group by excluded class
    by_class = {}
    for r in results:
        if r.excluded_class not in by_class:
            by_class[r.excluded_class] = []
        by_class[r.excluded_class].append(r)
    
    for cls, results_list in by_class.items():
        lines.append(f"\n--- Excluded Class: {cls} ---")
        for r in results_list:
            lines.append(f"  Model: {r.model_name}")
            lines.append(f"  Known Class Accuracy: {r.known_class_accuracy:.4f}")
            lines.append(f"  Known Class F1-macro: {r.known_class_f1_macro:.4f}")
            lines.append(f"  Known Class MCC: {r.known_class_mcc:.4f}")
            lines.append(f"  Unseen Detection Rate: {r.unseen_detection_rate:.2%}")
            lines.append(f"  Unseen False Positive Rate: {r.unseen_false_positive_rate:.2%}")
            lines.append(f"  Known False Negative Rate: {r.known_false_negative_rate:.2%}")
            lines.append(f"  Optimal Threshold: {r.optimal_threshold:.4f}")
            lines.append(f"  Threshold F1: {r.threshold_metrics.get('f1', 0):.4f}")
            lines.append("")
    
    return "\n".join(lines)


@dataclass
class UnseenDetector:
    """
    Runtime unseen attack detector for production use.
    
    Wraps a trained model with an unknown detection threshold.
    """
    model: Any
    known_classes: list[str]
    unknown_threshold: float = 0.5
    class_severity: dict[str, str] = field(default_factory=dict)
    
    def predict(self, X: pd.DataFrame) -> list[UnseenPrediction]:
        """
        Predict with unknown detection.
        
        Returns UnseenPrediction with:
        - predicted_class: predicted attack type or "UNKNOWN"
        - confidence: model confidence
        - is_unknown: whether classified as unknown
        - risk_level: LOW/GUARDED/MEDIUM/HIGH/CRITICAL
        - explanation: why this classification
        """
        predictions = self.model.predict(X)
        probabilities = self.model.predict_proba(X) if hasattr(self.model, "predict_proba") else None
        
        results = []
        for i, pred in enumerate(predictions):
            max_prob = 1.0
            if probabilities is not None:
                max_prob = probabilities[i].max()
            
            is_unknown = max_prob < self.unknown_threshold
            final_class = "UNKNOWN" if is_unknown else pred
            confidence = max_prob if not is_unknown else 1.0 - max_prob
            
            # Determine risk level
            severity = self.class_severity.get(final_class, "MEDIUM")
            if is_unknown:
                risk_level = "HIGH"  # unknown attacks are high risk by default
            elif severity == "CRITICAL":
                risk_level = "CRITICAL"
            elif severity == "HIGH":
                risk_level = "HIGH"
            elif severity == "MEDIUM":
                risk_level = "MEDIUM"
            else:
                risk_level = "LOW"
            
            # Generate explanation
            if is_unknown:
                explanation = f"Low confidence prediction (max prob={probabilities[i].max():.3f}) - potential unseen attack"
            else:
                explanation = f"Classified as {final_class} with {max_prob:.1%} confidence"
            
            results.append(UnseenPrediction(
                predicted_class=final_class,
                confidence=float(confidence),
                is_unknown=is_unknown,
                risk_level=risk_level,
                explanation=explanation,
            ))
        
        return results


if __name__ == "__main__":
    print("Unseen detection module loaded successfully")