"""
Model evaluation for the CIC-IDS2017 intrusion detection pipeline: accuracy,
precision, recall, F1, confusion matrix, ROC curve, precision-recall curve,
and full classification report.

This module is a direct, function-based conversion of the notebook's
evaluation cells:

    Notebook cell 126        -> imports (confusion_matrix, accuracy_score,
                                 classification_report, roc_auc_score,
                                 roc_curve, auc, precision_recall_curve)
    Notebook cells 128, 143,
    150, 155, 160, 169        -> compute_confusion_matrix()
    Notebook cells 129, 136,
    144                       -> compute_roc_curve()
    Notebook cells 130, 137,
    145                       -> compute_precision_recall_curve()
    Notebook cells 131, 132,
    151-153, 156-158, 161-163,
    168                       -> compute_classification_metrics(), evaluate_model()

Deliberate difference from the notebook: the notebook's evaluation cells
are inseparable from their matplotlib/seaborn plotting (heatmaps, ROC plots,
bar charts all in the same cell as the metric computation). This module
keeps the *computation* only and returns plain data (dicts, arrays, lists)
so it can be consumed by a FastAPI response, a report generator (Phase 10),
or a dashboard chart (Phase 6) - none of which want a matplotlib Figure.
Plotting itself is a presentation concern that belongs in those later
layers, not in the ML layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    auc,
    classification_report,
    confusion_matrix,
    precision_recall_curve,
    roc_auc_score,
    roc_curve,
)

from backend.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class EvaluationResult:
    """
    Full evaluation of one model against one test set. JSON-serializable
    via as_dict() for API responses / report generation.
    """

    model_name: str
    accuracy: float
    precision_macro: float
    recall_macro: float
    f1_macro: float
    classification_report: dict
    confusion_matrix: list[list[int]]
    labels: list[str]
    roc_auc: Optional[float] = None
    roc_curve: Optional[dict] = None  # {"fpr": [...], "tpr": [...], "thresholds": [...]}
    precision_recall_curve: Optional[dict] = None  # {"precision": [...], "recall": [...], "thresholds": [...]}
    cv_mean_score: Optional[float] = None
    cv_scores: list[float] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "model_name": self.model_name,
            "accuracy": self.accuracy,
            "precision_macro": self.precision_macro,
            "recall_macro": self.recall_macro,
            "f1_macro": self.f1_macro,
            "classification_report": self.classification_report,
            "confusion_matrix": self.confusion_matrix,
            "labels": self.labels,
            "roc_auc": self.roc_auc,
            "roc_curve": self.roc_curve,
            "precision_recall_curve": self.precision_recall_curve,
            "cv_mean_score": self.cv_mean_score,
            "cv_scores": self.cv_scores,
        }


def compute_classification_metrics(
    y_true: pd.Series | np.ndarray,
    y_pred: pd.Series | np.ndarray,
    target_names: Optional[list[str]] = None,
) -> dict:
    """
    Compute accuracy, macro precision/recall/F1, and the full per-class
    classification report.

    Converted from notebook cells 131-132 / 151-153 / 156-158 / 161-163 /
    168 (`classification_report(..., output_dict=True)`,
    `accuracy_score(...)`).

    Returns:
        {
          "accuracy": float,
          "precision_macro": float, "recall_macro": float, "f1_macro": float,
          "report": dict,   # sklearn's per-class classification_report dict
        }
    """
    report = classification_report(
        y_true=y_true, y_pred=y_pred, target_names=target_names, output_dict=True, zero_division=0
    )
    accuracy = float(accuracy_score(y_true, y_pred))

    macro = report.get("macro avg", {})
    return {
        "accuracy": accuracy,
        "precision_macro": float(macro.get("precision", 0.0)),
        "recall_macro": float(macro.get("recall", 0.0)),
        "f1_macro": float(macro.get("f1-score", 0.0)),
        "report": report,
    }


def compute_confusion_matrix(
    y_true: pd.Series | np.ndarray,
    y_pred: pd.Series | np.ndarray,
    labels: Optional[list[str]] = None,
) -> np.ndarray:
    """
    Compute the confusion matrix.

    Converted from notebook cells 128, 143, 150, 155, 160, 169
    (`confusion_matrix(y_test, y_pred)`).
    """
    return confusion_matrix(y_true, y_pred, labels=labels)


def compute_roc_curve(y_true: pd.Series | np.ndarray, y_prob: np.ndarray) -> dict:
    """
    Compute the ROC curve and AUC for a binary classifier.

    Converted from notebook cells 129, 136, 144:
        fpr, tpr, _ = roc_curve(y_test_bc, y_prob)
        roc_auc = auc(fpr, tpr)

    Args:
        y_true: True binary labels (0/1).
        y_prob: Predicted probability of the positive class, e.g.
            `model.predict_proba(X_test)[:, 1]`.

    Returns:
        {"fpr": [...], "tpr": [...], "thresholds": [...], "auc": float}
    """
    fpr, tpr, thresholds = roc_curve(y_true, y_prob)
    roc_auc = float(auc(fpr, tpr))
    return {
        "fpr": fpr.tolist(),
        "tpr": tpr.tolist(),
        "thresholds": thresholds.tolist(),
        "auc": roc_auc,
    }


def compute_precision_recall_curve(y_true: pd.Series | np.ndarray, y_prob: np.ndarray) -> dict:
    """
    Compute the precision-recall curve for a binary classifier.

    Converted from notebook cells 130, 137, 145:
        precision, recall, threshold = precision_recall_curve(y_test_bc, y_prob)
    """
    precision, recall, thresholds = precision_recall_curve(y_true, y_prob)
    return {
        "precision": precision.tolist(),
        "recall": recall.tolist(),
        "thresholds": thresholds.tolist(),
    }


def evaluate_model(
    model_name: str,
    model: Any,
    X_test: pd.DataFrame,
    y_test: pd.Series,
    cv_scores: Optional[np.ndarray] = None,
    positive_class_index: int = 1,
) -> EvaluationResult:
    """
    Run the full evaluation suite for one trained model against a test set,
    combining every metric the notebook computed for that model across its
    evaluation cells.

    ROC / precision-recall curves are only computed for binary classifiers
    that expose `predict_proba` (they're undefined for a plain multi-class
    label in the notebook's sense - the notebook itself only plots them for
    the binary LR/SVM models, not for RF/DT/KNN).

    Args:
        model_name: Human-readable name, e.g. "random_forest_2".
        model: A fitted classifier (from training.py).
        X_test: Held-out feature matrix.
        y_test: Held-out true labels.
        cv_scores: Optional cross-validation scores from training (attached
            to the result for a single combined report).
        positive_class_index: Column index of the positive class in
            `predict_proba`'s output, for ROC/PR curves (default 1, matching
            the notebook's `predict_proba(X_test_bc)[:, 1]`).

    Returns:
        An EvaluationResult with every computed metric.
    """
    y_pred = model.predict(X_test)
    labels = sorted(pd.Series(y_test).unique().tolist(), key=str)
    target_names = [str(label) for label in labels]

    metrics = compute_classification_metrics(y_test, y_pred, target_names=target_names)
    cm = compute_confusion_matrix(y_test, y_pred, labels=labels)

    roc_data = None
    roc_auc_value = None
    pr_data = None

    is_binary = len(labels) == 2
    if is_binary and hasattr(model, "predict_proba"):
        y_prob = model.predict_proba(X_test)[:, positive_class_index]
        roc_data = compute_roc_curve(y_test, y_prob)
        roc_auc_value = roc_data["auc"]
        pr_data = compute_precision_recall_curve(y_test, y_prob)

    result = EvaluationResult(
        model_name=model_name,
        accuracy=metrics["accuracy"],
        precision_macro=metrics["precision_macro"],
        recall_macro=metrics["recall_macro"],
        f1_macro=metrics["f1_macro"],
        classification_report=metrics["report"],
        confusion_matrix=cm.tolist(),
        labels=target_names,
        roc_auc=roc_auc_value,
        roc_curve=roc_data,
        precision_recall_curve=pr_data,
        cv_mean_score=float(cv_scores.mean()) if cv_scores is not None else None,
        cv_scores=cv_scores.tolist() if cv_scores is not None else [],
    )

    logger.info(
        "Evaluated %s: accuracy=%.4f, precision_macro=%.4f, recall_macro=%.4f, f1_macro=%.4f",
        model_name,
        result.accuracy,
        result.precision_macro,
        result.recall_macro,
        result.f1_macro,
    )
    return result


def compare_models(results: list[EvaluationResult]) -> list[dict]:
    """
    Rank a list of EvaluationResults by accuracy (descending), matching the
    notebook's model-comparison cells (e.g. 166-167: comparing RF/DT/KNN
    accuracy and mean CV score side by side).

    Returns a list of {"model_name", "accuracy", "f1_macro", "cv_mean_score"}
    dicts, best model first.
    """
    ranked = sorted(results, key=lambda r: r.accuracy, reverse=True)
    return [
        {
            "model_name": r.model_name,
            "accuracy": r.accuracy,
            "f1_macro": r.f1_macro,
            "cv_mean_score": r.cv_mean_score,
        }
        for r in ranked
    ]
