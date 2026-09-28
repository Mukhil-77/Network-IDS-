"""
Threshold Tuning for FP/FN Reduction

Implements configurable detection sensitivity with measurable trade-offs:
- LOW sensitivity: fewer false alarms, more missed attacks
- BALANCED: default operating point
- HIGH sensitivity: fewer missed attacks, more false alarms

Provides threshold optimization and comparison framework.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Callable
from collections import defaultdict

import numpy as np
import pandas as pd

from backend.ml.evaluation import EvaluationResult, evaluate_model
from backend.ml.training import prepare_multiclass_dataset, train_all_multiclass_models
from backend.ml.confidence import compute_confidence
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class SensitivityLevel:
    """Detection sensitivity levels."""
    LOW = "LOW"        # Conservative: fewer false positives, more false negatives
    BALANCED = "BALANCED"  # Default operating point
    HIGH = "HIGH"      # Aggressive: fewer false negatives, more false positives


@dataclass
class ThresholdConfig:
    """Configuration for detection threshold."""
    sensitivity: str = "BALANCED"
    confidence_threshold: float = 0.5  # Minimum confidence for positive prediction
    class_thresholds: dict[str, float] = None  # Per-class thresholds
    
    def __post_init__(self):
        if self.class_thresholds is None:
            self.class_thresholds = {}


@dataclass
class ThresholdMetrics:
    """Metrics at a specific threshold."""
    threshold: float
    accuracy: float
    precision: float
    recall: float
    f1: float
    fpr: float
    fnr: float
    precision_macro: float
    recall_macro: float
    f1_macro: float
    mcc: float
    per_class_precision: dict[str, float]
    per_class_recall: dict[str, float]
    per_class_f1: dict[str, float]


@dataclass
class ThresholdComparison:
    """Comparison of multiple threshold configurations."""
    baseline: ThresholdMetrics
    optimized: ThresholdMetrics
    improvement: dict[str, float]
    sensitivity: str


class ThresholdOptimizer:
    """
    Optimizes detection thresholds for different sensitivity levels.
    
    Provides:
    - Baseline threshold (0.5)
    - Optimized threshold per sensitivity level
    - Per-class threshold optimization
    - FPR/FNR trade-off analysis
    """
    
    def __init__(self, model: Any, X_test: pd.DataFrame, y_test: pd.Series):
        self.model = model
        self.X_test = X_test
        self.y_test = y_test
        self.classes_ = sorted(pd.Series(y_test).unique().tolist(), key=str)
        
        # Get prediction probabilities
        self.y_prob = model.predict_proba(X_test) if hasattr(model, "predict_proba") else None
        self.y_pred_default = model.predict(X_test)
        
        # Ensure probability columns align with classes
        if self.y_prob is not None and hasattr(model, "classes_"):
            prob_df = pd.DataFrame(self.y_prob, columns=[str(c) for c in model.classes_])
            # Reorder to match self.classes_
            self.y_prob = prob_df[sorted(model.classes_, key=str)].values
    
    def apply_threshold(self, y_prob: np.ndarray, threshold: float, class_thresholds: dict = None) -> np.ndarray:
        """
        Apply threshold to prediction probabilities.
        
        Args:
            y_prob: Prediction probabilities (n_samples, n_classes)
            threshold: Global threshold for positive class
            class_thresholds: Optional per-class thresholds
            
        Returns:
            Predicted class labels with threshold applied
        """
        if class_thresholds is None:
            class_thresholds = {}
        
        predictions = []
        for i in range(len(y_prob)):
            probs = y_prob[i]
            max_prob = probs.max()
            max_class_idx = probs.argmax()
            max_class = self.classes_[max_class_idx]
            
            # Check class-specific threshold
            class_threshold = class_thresholds.get(max_class, threshold)
            
            if max_prob >= class_threshold:
                predictions.append(self.classes_[max_class_idx])
            else:
                # Below threshold - classify as BENIGN or UNKNOWN
                predictions.append("BENIGN")
        
        return np.array(predictions)
    
    def evaluate_threshold(self, threshold: float, class_thresholds: dict = None) -> ThresholdMetrics:
        """Evaluate metrics at a specific threshold."""
        y_pred = self.apply_threshold(self.y_prob, threshold, class_thresholds)
        
        # Use existing evaluation function
        from backend.ml.evaluation import evaluate_model
        # We need to create a mock model that returns our thresholded predictions
        class MockModel:
            def __init__(self, y_pred):
                self._y_pred = y_pred
            def predict(self, X):
                return self._y_pred
            def predict_proba(self, X):
                return self.y_prob
        
        mock_model = MockModel(y_pred)
        mock_model.y_prob = self.y_prob
        
        # Use the existing evaluation function
        from backend.ml.evaluation import evaluate_model, compute_confusion_matrix, compute_classification_metrics
        y_true = self.y_test
        y_pred_labels = y_pred
        
        labels = sorted(pd.Series(self.y_test).unique().tolist(), key=str)
        target_names = [str(l) for l in labels]
        
        # Compute metrics
        metrics = compute_classification_metrics(y_true, y_pred_labels, target_names=target_names)
        cm = np.array(compute_confusion_matrix(y_true, y_pred_labels, labels=labels))
        fpr_dict, fnr_dict = compute_per_class_fpr_fnr(cm, labels)
        
        # Per-class metrics
        per_class_precision = {}
        per_class_recall = {}
        per_class_f1 = {}
        for cls in labels:
            cls_mask = (y_true == cls)
            if cls_mask.sum() > 0:
                from sklearn.metrics import precision_score, recall_score, f1_score
                # For multiclass, we need to use a different approach
                # Create binary labels for this class vs rest
                y_true_binary = (y_true == cls).astype(int)
                y_pred_binary = (y_pred_labels == cls).astype(int)
                per_class_precision[cls] = float(precision_score(y_true_binary, y_pred_binary, zero_division=0))
                per_class_recall[cls] = float(recall_score(y_true_binary, y_pred_binary, zero_division=0))
                per_class_f1[cls] = float(f1_score(y_true_binary, y_pred_binary, zero_division=0))
        
        return ThresholdMetrics(
            threshold=threshold,
            accuracy=metrics["accuracy"],
            precision=metrics["precision_macro"],
            recall=metrics["recall_macro"],
            f1=metrics["f1_macro"],
            fpr=np.mean(list(compute_per_class_fpr_fnr(cm, labels)[0].values())),
            fnr=np.mean(list(compute_per_class_fpr_fnr(cm, labels)[1].values())),
            precision_macro=metrics["precision_macro"],
            recall_macro=metrics["recall_macro"],
            f1_macro=metrics["f1_macro"],
            mcc=metrics["mcc"],
            per_class_precision=per_class_precision,
            per_class_recall=per_class_recall,
            per_class_f1=per_class_f1,
        )
    
    def find_optimal_threshold(
        self, 
        metric: str = "f1_macro",
        class_thresholds: dict = None,
        threshold_range: tuple = (0.1, 0.9),
        steps: int = 50
    ) -> tuple[float, ThresholdMetrics]:
        """
        Find optimal threshold for a given metric.
        
        Args:
            metric: Metric to optimize (f1_macro, recall_macro, precision_macro, mcc)
            class_thresholds: Optional per-class thresholds
            threshold_range: (min, max) threshold range
            steps: Number of thresholds to test
            
        Returns:
            (optimal_threshold, metrics_at_threshold)
        """
        thresholds = np.linspace(threshold_range[0], threshold_range[1], steps)
        best_threshold = 0.5
        best_metrics = None
        best_score = -1
        
        for t in thresholds:
            metrics = self.evaluate_threshold(t)
            score = getattr(metrics, metric, 0)
            if score > best_score:
                best_score = score
                best_threshold = t
                best_metrics = metrics
        
        return best_threshold, best_metrics
    
    def get_sensitivity_thresholds(self) -> dict[str, ThresholdConfig]:
        """
        Get pre-defined threshold configurations for each sensitivity level.
        
        Returns:
            Dict mapping sensitivity level to ThresholdConfig
        """
        return {
            SensitivityLevel.LOW: ThresholdConfig(
                sensitivity="LOW",
                confidence_threshold=0.7,
                class_thresholds={}  # would be optimized
            ),
            SensitivityLevel.BALANCED: ThresholdConfig(
                sensitivity="BALANCED",
                confidence_threshold=0.5,
                class_thresholds={}
            ),
            SensitivityLevel.HIGH: ThresholdConfig(
                sensitivity="HIGH",
                confidence_threshold=0.3,
                class_thresholds={}
            ),
        }
    
    def compare_sensitivities(self) -> dict[str, ThresholdMetrics]:
        """Compare performance across all sensitivity levels."""
        configs = self.get_sensitivity_thresholds()
        results = {}
        
        for level, config in configs.items():
            metrics = self.evaluate_threshold(config.confidence_threshold)
            results[level] = metrics
            logger.info(f"{level}: accuracy={metrics.accuracy:.4f}, f1_macro={metrics.f1_macro:.4f}, "
                       f"fpr={metrics.fpr:.4f}, fnr={metrics.fnr:.4f}")
        
        return results
    
    def find_optimal_per_class_thresholds(self, metric: str = "f1") -> dict[str, float]:
        """
        Find optimal threshold per class.
        
        Returns:
            Dict mapping class name to optimal threshold
        """
        optimal_thresholds = {}
        
        for cls in self.classes_:
            # For each class, find threshold that maximizes the metric
            # This is a simplified version - would need more sophisticated optimization
            best_t = 0.5
            best_score = 0
            
            for t in np.linspace(0.1, 0.9, 20):
                class_thresholds = {cls: t for cls in self.classes_}
                # This is simplified - in practice would optimize per class independently
                pass
            
            optimal_thresholds[cls] = 0.5  # placeholder
        
        return optimal_thresholds


def compute_per_class_fpr_fnr(cm: np.ndarray, labels: list[str]) -> tuple[dict[str, float], dict[str, float]]:
    """Compute per-class FPR and FNR from confusion matrix."""
    n_classes = cm.shape[0]
    fpr = {}
    fnr = {}
    
    for i, label in enumerate(labels):
        tp = cm[i, i]
        fn = cm[i, :].sum() - tp
        fp = cm[:, i].sum() - tp
        tn = cm.sum() - tp - fn - fp
        
        fpr[label] = float(fp / (fp + tn)) if (fp + tn) > 0 else 0.0
        fnr[label] = float(fn / (fn + tp)) if (fn + tp) > 0 else 0.0
    
    return fpr, fnr


@dataclass
class ThresholdExperiment:
    """Container for threshold tuning experiment results."""
    sensitivity: str
    config: ThresholdConfig
    baseline_metrics: ThresholdMetrics
    optimized_metrics: ThresholdMetrics
    improvement: dict[str, float]


def run_threshold_experiment(
    model: Any,
    X_test: pd.DataFrame,
    y_test: pd.Series,
    sensitivities: list[str] = None,
) -> dict[str, ThresholdExperiment]:
    """
    Run threshold tuning experiment for multiple sensitivity levels.
    
    Returns:
        Dict mapping sensitivity level to experiment results
    """
    if sensitivities is None:
        sensitivities = [SensitivityLevel.LOW, SensitivityLevel.BALANCED, SensitivityLevel.HIGH]
    
    optimizer = ThresholdOptimizer(model, X_test, y_test)
    results = {}
    
    # Get baseline (default threshold 0.5)
    baseline_metrics = optimizer.evaluate_threshold(0.5)
    
    for sensitivity in sensitivities:
        config = ThresholdConfig(sensitivity=sensitivity)
        config.confidence_threshold = {
            "LOW": 0.7,
            "BALANCED": 0.5,
            "HIGH": 0.3,
        }[sensitivity]
        
        optimized_metrics = optimizer.evaluate_threshold(config.confidence_threshold)
        
        # Compute improvements
        baseline_f1 = optimizer.evaluate_threshold(0.5).f1_macro
        optimized_f1 = optimizer.evaluate_threshold(config.confidence_threshold).f1_macro
        
        improvement = {
            "accuracy": optimizer.evaluate_threshold(config.confidence_threshold).accuracy - 
                       optimizer.evaluate_threshold(0.5).accuracy,
            "f1_macro": optimized_f1 - baseline_f1,
            "precision_macro": optimizer.evaluate_threshold(config.confidence_threshold).precision_macro - 
                              optimizer.evaluate_threshold(0.5).precision_macro,
            "recall_macro": optimizer.evaluate_threshold(config.confidence_threshold).recall_macro - 
                           optimizer.evaluate_threshold(0.5).recall_macro,
            "fpr_change": optimizer.evaluate_threshold(config.confidence_threshold).fpr - 
                          optimizer.evaluate_threshold(0.5).fpr,
            "fnr_change": optimizer.evaluate_threshold(config.confidence_threshold).fnr - 
                          optimizer.evaluate_threshold(0.5).fnr,
        }
        
        results[sensitivity] = ThresholdExperiment(
            sensitivity=sensitivity,
            config=config,
            baseline_metrics=optimizer.evaluate_threshold(0.5),
            optimized_metrics=optimizer.evaluate_threshold(config.confidence_threshold),
            improvement=improvement,
        )
    
    return results


def generate_threshold_report(experiments: dict[str, ThresholdExperiment]) -> str:
    """Generate human-readable threshold tuning report."""
    lines = []
    lines.append("=" * 80)
    lines.append("THRESHOLD TUNING REPORT")
    lines.append("=" * 80)
    
    for sensitivity, exp in experiments.items():
        b = exp.baseline_metrics
        o = exp.optimized_metrics
        imp = exp.improvement
        
        lines.append(f"\n--- {sensitivity} Sensitivity ---")
        lines.append(f"  Threshold: {exp.config.confidence_threshold:.2f}")
        lines.append(f"  Accuracy:  {b.accuracy:.4f} -> {o.accuracy:.4f} ({imp['accuracy']:+.4f})")
        lines.append(f"  F1-macro:  {b.f1_macro:.4f} -> {o.f1_macro:.4f} ({imp['f1_macro']:+.4f})")
        lines.append(f"  Precision: {b.precision_macro:.4f} -> {o.precision_macro:.4f} ({imp['precision_macro']:+.4f})")
        lines.append(f"  Recall:    {b.recall_macro:.4f} -> {o.recall_macro:.4f} ({imp['recall_macro']:+.4f})")
        lines.append(f"  FPR:       {b.fpr:.4f} -> {o.fpr:.4f} ({imp['fpr_change']:+.4f})")
        lines.append(f"  FNR:       {b.fnr:.4f} -> {o.fnr:.4f} ({imp['fnr_change']:+.4f})")
        lines.append(f"  MCC:       {b.mcc:.4f} -> {o.mcc:.4f}")
        lines.append("")
    
    return "\n".join(lines)


if __name__ == "__main__":
    print("Threshold tuning module loaded successfully")