"""
Model evaluation for the CIC-IDS2017 intrusion detection pipeline: accuracy,
precision, recall, F1, confusion matrix, ROC curve, precision-recall curve,
MCC, and full classification report with per-class metrics.

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

New additions (Phase 2 - research-grade evaluation):
- MCC (Matthews Correlation Coefficient)
- Per-class FPR, FNR, precision, recall, F1
- Multi-class PR-AUC (one-vs-rest)
- False Positive Rate / False Negative Rate per class
- Weighted-F1
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    auc,
    average_precision_score,
    balanced_accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    matthews_corrcoef,
    precision_recall_curve,
    precision_score,
    recall_score,
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
    balanced_accuracy: float
    precision_macro: float
    recall_macro: float
    f1_macro: float
    f1_weighted: float
    precision_micro: float
    recall_micro: float
    f1_micro: float
    mcc: float
    classification_report: dict
    confusion_matrix: list[list[int]]
    labels: list[str]
    per_class_precision: dict[str, float]
    per_class_recall: dict[str, float]
    per_class_f1: dict[str, float]
    per_class_support: dict[str, int]
    per_class_fpr: dict[str, float]
    per_class_fnr: dict[str, float]
    roc_auc: Optional[float] = None
    roc_auc_ovr: Optional[float] = None
    roc_auc_ovo: Optional[float] = None
    roc_curve: Optional[dict] = None
    pr_auc: Optional[float] = None
    pr_auc_ovr: Optional[float] = None
    precision_recall_curve: Optional[dict] = None
    cv_mean_score: Optional[float] = None
    cv_scores: list[float] = field(default_factory=list)
    fpr_macro: float = 0.0
    fnr_macro: float = 0.0

    def as_dict(self) -> dict:
        return {
            "model_name": self.model_name,
            "accuracy": self.accuracy,
            "balanced_accuracy": self.balanced_accuracy,
            "precision_macro": self.precision_macro,
            "recall_macro": self.recall_macro,
            "f1_macro": self.f1_macro,
            "f1_weighted": self.f1_weighted,
            "precision_micro": self.precision_micro,
            "recall_micro": self.recall_micro,
            "f1_micro": self.f1_micro,
            "mcc": self.mcc,
            "classification_report": self.classification_report,
            "confusion_matrix": self.confusion_matrix,
            "labels": self.labels,
            "roc_auc": self.roc_auc,
            "roc_auc_ovr": self.roc_auc_ovr,
            "roc_auc_ovo": self.roc_auc_ovo,
            "roc_curve": self.roc_curve,
            "pr_auc": self.pr_auc,
            "pr_auc_ovr": self.pr_auc_ovr,
            "precision_recall_curve": self.precision_recall_curve,
            "cv_mean_score": self.cv_mean_score,
            "cv_scores": self.cv_scores,
            "fpr_macro": self.fpr_macro,
            "fnr_macro": self.fnr_macro,
            "per_class_precision": self.per_class_precision,
            "per_class_recall": self.per_class_recall,
            "per_class_f1": self.per_class_f1,
            "per_class_support": self.per_class_support,
            "per_class_fpr": self.per_class_fpr,
            "per_class_fnr": self.per_class_fnr,
        }


def compute_per_class_fpr_fnr(cm: np.ndarray, labels: list[str]) -> tuple[dict[str, float], dict[str, float]]:
    """
    Compute per-class False Positive Rate and False Negative Rate from confusion matrix.
    
    FPR = FP / (FP + TN) = FP / (total actual negatives)
    FNR = FN / (FN + TP) = FN / (total actual positives)
    """
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


def compute_classification_metrics(
    y_true: pd.Series | np.ndarray,
    y_pred: pd.Series | np.ndarray,
    target_names: Optional[list[str]] = None,
) -> dict:
    """
    Compute comprehensive classification metrics including:
    - Accuracy, balanced accuracy
    - Precision/Recall/F1 (macro, micro, weighted)
    - Matthews Correlation Coefficient (MCC)
    - Per-class precision, recall, F1, support
    - Per-class FPR, FNR
    - FPR/FNR macro averages
    """
    report = classification_report(
        y_true=y_true, y_pred=y_pred, target_names=target_names, output_dict=True, zero_division=0
    )
    accuracy = float(accuracy_score(y_true, y_pred))
    balanced_acc = float(balanced_accuracy_score(y_true, y_pred))
    mcc = float(matthews_corrcoef(y_true, y_pred))

    macro = report.get("macro avg", {})
    weighted = report.get("weighted avg", {})
    
    precision_macro = float(macro.get("precision", 0.0))
    recall_macro = float(macro.get("recall", 0.0))
    f1_macro = float(macro.get("f1-score", 0.0))
    f1_weighted = float(weighted.get("f1-score", 0.0))
    
    precision_micro = float(precision_score(y_true, y_pred, average='micro', zero_division=0))
    recall_micro = float(recall_score(y_true, y_pred, average='micro', zero_division=0))
    f1_micro = float(f1_score(y_true, y_pred, average='micro', zero_division=0))

    labels = sorted(pd.Series(y_true).unique().tolist(), key=str)
    
    # Per-class metrics from report
    per_class_precision = {}
    per_class_recall = {}
    per_class_f1 = {}
    per_class_support = {}
    
    for label in labels:
        label_str = str(label)
        if label_str in report:
            per_class_precision[label_str] = float(report[label_str].get("precision", 0.0))
            per_class_recall[label_str] = float(report[label_str].get("recall", 0.0))
            per_class_f1[label_str] = float(report[label_str].get("f1-score", 0.0))
            per_class_support[label_str] = int(report[label_str].get("support", 0))
        else:
            per_class_precision[label_str] = 0.0
            per_class_recall[label_str] = 0.0
            per_class_f1[label_str] = 0.0
            per_class_support[label_str] = 0
    
    # Compute per-class FPR and FNR from confusion matrix
    cm = confusion_matrix(y_true, y_pred, labels=labels)
    per_class_fpr = {}
    per_class_fnr = {}
    
    for i, label in enumerate(labels):
        label_str = str(label)
        TP = cm[i, i]
        FP = cm[:, i].sum() - TP
        FN = cm[i, :].sum() - TP
        TN = cm.sum() - TP - FP - FN
        
        fpr = FP / (FP + TN) if (FP + TN) > 0 else 0.0
        fnr = FN / (FN + TP) if (FN + TP) > 0 else 0.0
        
        per_class_fpr[label_str] = float(fpr)
        per_class_fnr[label_str] = float(fnr)
    
    fpr_macro = float(np.mean(list(per_class_fpr.values())))
    fnr_macro = float(np.mean(list(per_class_fnr.values())))
    
    return {
        "accuracy": accuracy,
        "balanced_accuracy": balanced_acc,
        "precision_macro": precision_macro,
        "recall_macro": recall_macro,
        "f1_macro": f1_macro,
        "f1_weighted": f1_weighted,
        "precision_micro": precision_micro,
        "recall_micro": recall_micro,
        "f1_micro": f1_micro,
        "mcc": mcc,
        "report": report,
        "per_class_precision": per_class_precision,
        "per_class_recall": per_class_recall,
        "per_class_f1": per_class_f1,
        "per_class_support": per_class_support,
        "per_class_fpr": per_class_fpr,
        "per_class_fnr": per_class_fnr,
        "fpr_macro": fpr_macro,
        "fnr_macro": fnr_macro,
    }


def compute_confusion_matrix(
    y_true: pd.Series | np.ndarray,
    y_pred: pd.Series | np.ndarray,
    labels: Optional[list[str]] = None,
) -> np.ndarray:
    """
    Compute the confusion matrix.
    """
    return confusion_matrix(y_true, y_pred, labels=labels)


def compute_roc_curve(y_true: pd.Series | np.ndarray, y_prob: np.ndarray) -> dict:
    """
    Compute the ROC curve and AUC for a binary classifier.
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
    """
    precision, recall, thresholds = precision_recall_curve(y_true, y_prob)
    pr_auc = float(auc(recall, precision))
    return {
        "precision": precision.tolist(),
        "recall": recall.tolist(),
        "thresholds": thresholds.tolist(),
        "auc": pr_auc,
    }


def compute_multiclass_pr_auc(y_true: pd.Series | np.ndarray, y_prob: np.ndarray, labels: list[str]) -> tuple[float, dict]:
    """
    Compute multi-class PR-AUC using one-vs-rest strategy.
    
    Returns:
        (macro_pr_auc, per_class_curves_dict)
    """
    from sklearn.preprocessing import label_binarize
    
    y_true_bin = label_binarize(y_true, classes=labels)
    n_classes = len(labels)
    
    per_class = {}
    pr_aucs = []
    
    for i, label in enumerate(labels):
        if y_prob.shape[1] <= i:
            continue
        precision, recall, thresholds = precision_recall_curve(y_true_bin[:, i], y_prob[:, i])
        pr_auc = float(auc(recall, precision))
        pr_aucs.append(pr_auc)
        per_class[label] = {
            "precision": precision.tolist(),
            "recall": recall.tolist(),
            "thresholds": thresholds.tolist(),
            "auc": pr_auc,
        }
    
    macro_pr_auc = float(np.mean(pr_aucs)) if pr_aucs else 0.0
    return macro_pr_auc, per_class


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
    combining every metric the notebook computed plus new research-grade metrics.
    """
    y_pred = model.predict(X_test)
    labels = sorted(pd.Series(y_test).unique().tolist(), key=str)
    target_names = [str(label) for label in labels]
    
    # Determine if binary classification
    is_binary = len(labels) == 2

    metrics = compute_classification_metrics(y_test, y_pred, target_names=target_names)
    cm = compute_confusion_matrix(y_test, y_pred, labels=labels)
    fpr_dict, fnr_dict = compute_per_class_fpr_fnr(cm, labels)
    
    # Initialize all ROC/PR AUC variables
    roc_data = None
    roc_auc_value = None
    roc_auc_ovr = None
    roc_auc_ovo = None
    pr_data = None
    pr_auc_value = None
    pr_auc_ovr = None
    pr_curves = None
    
    is_binary = len(labels) == 2
    if is_binary and hasattr(model, "predict_proba"):
        y_prob = model.predict_proba(X_test)[:, positive_class_index]
        roc_data = compute_roc_curve(y_test, y_prob)
        roc_auc_value = roc_data["auc"]
        pr_data = compute_precision_recall_curve(y_test, y_prob)
        pr_auc_value = pr_data["auc"]
    elif hasattr(model, "predict_proba"):
        # Multi-class with predict_proba
        y_prob = model.predict_proba(X_test)
        # Ensure columns align with labels
        if hasattr(model, "classes_"):
            prob_labels = [str(c) for c in model.classes_]
            # Reorder columns to match labels order
            prob_df = pd.DataFrame(y_prob, columns=prob_labels)
            y_prob = prob_df[labels].values
        else:
            y_prob = y_prob[:, :len(labels)]
        
        # Multi-class PR-AUC (one-vs-rest)
        pr_auc_value, pr_curves = compute_multiclass_pr_auc(y_test, y_prob, labels)
        # Multi-class ROC-AUC (one-vs-rest and one-vs-one)
        try:
            roc_auc_ovr = float(roc_auc_score(y_test, y_prob, multi_class='ovr', average='macro'))
            roc_auc_ovo = float(roc_auc_score(y_test, y_prob, multi_class='ovo', average='macro'))
        except Exception as e:
            logger.warning(f"Could not compute multi-class ROC-AUC: {e}")
            roc_auc_ovr = None
            roc_auc_ovo = None
        
        # Multi-class PR-AUC (one-vs-rest)
        try:
            from sklearn.metrics import average_precision_score
            pr_aucs = []
            for i in range(len(labels)):
                y_true_binary = (y_test == labels[i]).astype(int)
                y_prob_class = y_prob[:, i]
                if len(np.unique(y_true_binary)) > 1:
                    ap = average_precision_score(y_true_binary, y_prob_class)
                    pr_aucs.append(ap)
            pr_auc_ovr = float(np.mean(pr_aucs)) if pr_aucs else None
        except Exception as e:
            logger.warning(f"Could not compute multi-class PR-AUC: {e}")
            pr_auc_ovr = None

    result = EvaluationResult(
        model_name=model_name,
        accuracy=metrics["accuracy"],
        balanced_accuracy=metrics["balanced_accuracy"],
        precision_macro=metrics["precision_macro"],
        recall_macro=metrics["recall_macro"],
        f1_macro=metrics["f1_macro"],
        f1_weighted=metrics["f1_weighted"],
        precision_micro=metrics["precision_micro"],
        recall_micro=metrics["recall_micro"],
        f1_micro=metrics["f1_micro"],
        mcc=metrics["mcc"],
        classification_report=metrics["report"],
        confusion_matrix=cm.tolist(),
        labels=target_names,
        per_class_precision=metrics["per_class_precision"],
        per_class_recall=metrics["per_class_recall"],
        per_class_f1=metrics["per_class_f1"],
        per_class_support=metrics["per_class_support"],
        per_class_fpr=metrics["per_class_fpr"],
        per_class_fnr=metrics["per_class_fnr"],
        roc_auc=roc_auc_value,
        roc_auc_ovr=roc_auc_ovr,
        roc_auc_ovo=roc_auc_ovo,
        roc_curve=roc_data,
        pr_auc=pr_auc_value,
        pr_auc_ovr=pr_auc_ovr,
        precision_recall_curve=pr_data if is_binary else pr_curves,
        cv_mean_score=float(cv_scores.mean()) if cv_scores is not None else None,
        cv_scores=cv_scores.tolist() if cv_scores is not None else [],
        fpr_macro=metrics["fpr_macro"],
        fnr_macro=metrics["fnr_macro"],
    )

    logger.info(
        "Evaluated %s: accuracy=%.4f, precision_macro=%.4f, recall_macro=%.4f, f1_macro=%.4f, f1_weighted=%.4f, mcc=%.4f",
        model_name,
        result.accuracy,
        result.precision_macro,
        result.recall_macro,
        result.f1_macro,
        result.f1_weighted,
        result.mcc,
    )
    return result


def compare_models(results: list[EvaluationResult]) -> list[dict]:
    """
    Rank a list of EvaluationResults by accuracy (descending), matching the
    notebook's model-comparison cells (e.g. 166-167: comparing RF/DT/KNN
    accuracy and mean CV score side by side).
    """
    ranked = sorted(results, key=lambda r: r.accuracy, reverse=True)
    return [
        {
            "model_name": r.model_name,
            "accuracy": r.accuracy,
            "f1_macro": r.f1_macro,
            "f1_weighted": r.f1_weighted,
            "mcc": r.mcc,
            "cv_mean_score": r.cv_mean_score,
        }
        for r in ranked
    ]
