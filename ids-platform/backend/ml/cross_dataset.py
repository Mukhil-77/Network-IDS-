"""
Cross-Dataset Generalization Experiments

Implements research-grade experiments for measuring domain shift between datasets:
- Train on CIC-IDS2017, test on UNSW-NB15 (and vice versa)
- Measure performance degradation
- Per-class degradation analysis
- FPR/FNR changes
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import numpy as np
import pandas as pd

from backend.ml.evaluation import EvaluationResult, evaluate_model
from backend.ml.training import prepare_multiclass_dataset, train_all_multiclass_models
from backend.ml.dataset_registry import (
    DatasetRegistry,
    DatasetConfig,
    FeatureMapping,
    dataset_registry,
)
from backend.ml.feature_engineering import FeatureEngineer
from backend.ml.artifacts import save_model_bundle
from backend.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class CrossDatasetResult:
    """Results from a cross-dataset generalization experiment."""
    train_dataset: str
    test_dataset: str
    model_name: str
    in_domain_result: 'EvaluationResult'
    cross_domain_result: 'EvaluationResult'
    degradation: dict[str, float]
    per_class_degradation: dict[str, dict[str, float]]
    fpr_change: dict[str, float]
    fnr_change: dict[str, float]
    feature_mapping: 'FeatureMapping'
    
    def to_dict(self) -> dict:
        return {
            "train_dataset": self.train_dataset,
            "test_dataset": self.test_dataset,
            "model_name": self.model_name,
            "in_domain": self.in_domain_result.as_dict(),
            "cross_domain": self.cross_domain_result.as_dict(),
            "degradation": self.degradation,
            "per_class_degradation": self.per_class_degradation,
            "fpr_change": self.fpr_change,
            "fnr_change": self.fnr_change,
            "feature_mapping": {
                "canonical_features_count": len(self.feature_mapping.canonical_features),
                "raw_to_canonical_count": len(self.feature_mapping.raw_to_canonical),
                "unmapped_raw_count": len(self.feature_mapping.unmapped_raw),
                "missing_canonical_count": len(self.feature_mapping.missing_canonical),
            }
        }


def compute_degradation(in_domain: 'EvaluationResult', cross_domain: 'EvaluationResult') -> dict[str, float]:
    """Compute metric degradation from in-domain to cross-domain."""
    return {
        "accuracy": in_domain.accuracy - cross_domain.accuracy,
        "precision_macro": in_domain.precision_macro - cross_domain.precision_macro,
        "recall_macro": in_domain.recall_macro - cross_domain.recall_macro,
        "f1_macro": in_domain.f1_macro - cross_domain.f1_macro,
        "f1_weighted": in_domain.f1_weighted - cross_domain.f1_weighted,
        "mcc": in_domain.mcc - cross_domain.mcc,
        "precision_macro_pct": ((in_domain.precision_macro - cross_domain.precision_macro) / max(in_domain.precision_macro, 1e-8)) * 100,
        "recall_macro_pct": ((in_domain.recall_macro - cross_domain.recall_macro) / max(in_domain.recall_macro, 1e-8)) * 100,
        "f1_macro_pct": ((in_domain.f1_macro - cross_domain.f1_macro) / max(in_domain.f1_macro, 1e-8)) * 100,
        "accuracy_pct": ((in_domain.accuracy - cross_domain.accuracy) / max(in_domain.accuracy, 1e-8)) * 100,
        "mcc_pct": ((in_domain.mcc - cross_domain.mcc) / max(abs(in_domain.mcc), 1e-8)) * 100,
    }


def compute_per_class_degradation(in_domain: 'EvaluationResult', cross_domain: 'EvaluationResult') -> dict[str, dict[str, float]]:
    """Compute per-class metric degradation."""
    in_report = in_domain.classification_report
    cross_report = cross_domain.classification_report
    
    degradation = {}
    for class_name in cross_domain.labels:
        if class_name in in_domain.classification_report and class_name in cross_domain.classification_report:
            in_class = in_domain.classification_report[class_name]
            cross_class = cross_domain.classification_report[class_name]
            degradation[class_name] = {
                "precision": in_class.get("precision", 0) - cross_class.get("precision", 0),
                "recall": in_class.get("recall", 0) - cross_class.get("recall", 0),
                "f1": in_class.get("f1-score", 0) - cross_class.get("f1-score", 0),
                "support": cross_class.get("support", 0),
            }
    return degradation


def compute_fpr_fnr_changes(in_domain: 'EvaluationResult', cross_domain: 'EvaluationResult') -> tuple[dict[str, float], dict[str, float]]:
    """Compute FPR and FNR changes."""
    fpr_changes = {}
    fnr_changes = {}
    
    for class_name in cross_domain.labels:
        if class_name in in_domain.per_class_fpr and class_name in cross_domain.per_class_fpr:
            fpr_changes[class_name] = cross_domain.per_class_fpr[class_name] - in_domain.per_class_fpr[class_name]
            fnr_changes[class_name] = cross_domain.per_class_fnr[class_name] - in_domain.per_class_fnr[class_name]
    
    return fpr_changes, fnr_changes


def run_cross_dataset_experiment(
    train_dataset_name: str,
    test_dataset_name: str,
    registry: 'DatasetRegistry' = None,
    model_filter: Optional[list[str]] = None,
) -> list[Any]:
    """
    Run cross-dataset generalization experiment.
    
    Train on train_dataset, test on test_dataset.
    """
    if registry is None:
        registry = dataset_registry
    
    train_config = registry.get(train_dataset_name)
    test_config = registry.get(test_dataset_name)
    
    if not train_config or not test_config:
        raise ValueError(f"Dataset not found: {train_dataset_name} or {test_dataset_name}")
    
    train_loader = registry.get_loader(train_dataset_name)
    test_loader = registry.get_loader(test_dataset_name)
    
    if not train_loader or not test_loader:
        raise ValueError(f"Loader not available for {train_dataset_name} or {test_dataset_name}")
    
    logger.info("Loading training data from %s...", train_config.name)
    train_df_raw = train_loader.load_raw(train_config.data_dir)
    train_df = train_loader.preprocess(train_df_raw)
    
    logger.info("Loading test data from %s...", test_config.name)
    test_df_raw = test_loader.load_raw(test_config.data_dir)
    test_df = test_loader.preprocess(test_df_raw)
    
    # Analyze feature compatibility
    feature_mapping = registry.analyze_feature_compatibility(train_config.name, test_config.name)
    logger.info("Feature compatibility: %d canonical features, %d unmapped, %d missing",
                len(feature_mapping.canonical_features), len(feature_mapping.unmapped_raw), len(feature_mapping.missing_canonical))
    
    # Feature engineering for both datasets
    # We need to use the SAME feature engineer (trained on train data) for both
    # For this, we'll use the canonical features as the common space
    
    # Prepare training dataset
    train_df_processed = train_config.preprocess_fn(train_config) if hasattr(train_config, 'preprocess_fn') else train_df
    test_df_processed = test_config.preprocess_fn(test_config) if hasattr(test_config, 'preprocess_fn') else test_config.preprocess(test_df)
    
    # Use canonical features for both
    canonical_features = feature_mapping.canonical_features
    if not canonical_features:
        logger.warning("No canonical features found, using all common numeric columns")
        # Fallback: use all numeric columns present in both
        train_numeric = train_df_processed.select_dtypes(include=[np.number]).columns.tolist()
        test_numeric = test_config.preprocess(test_loader.load_raw(test_config.data_dir).head(1000)).select_dtypes(include=[np.number]).columns.tolist()
        canonical_features = list(set(train_numeric) & set(test_numeric))
    
    # Filter to canonical features + target
    target_col = "Attack Type"
    train_features = [c for c in canonical_features if c in train_df_processed.columns]
    test_features = [c for c in canonical_features if c in test_config.preprocess(test_loader.load_raw(test_config.data_dir).head(1000)).columns]
    common_features = list(set(train_features) & set(test_features))
    
    if not common_features:
        raise ValueError("No common features found between datasets")
    
    logger.info("Using %d common features for cross-dataset experiment", len(common_features))
    
    # Prepare datasets with common features
    X_train = train_df_processed[common_features]
    y_train = train_df_processed["Attack Type"]
    X_test = test_df_processed[common_features]
    y_test = test_df_processed["Attack Type"]
    
    # Create datasets
    from backend.ml.training import Dataset
    train_dataset = type('Dataset', (), {
        'X_train': train_df_processed[common_features],
        'X_test': train_df_processed[common_features],  # not used for training
        'y_train': train_df_processed["Attack Type"],
        'y_test': train_df_processed["Attack Type"],
    })()
    
    # Train models
    logger.info("Training models on %s...", train_config.name)
    models = train_all_multiclass_models(train_dataset)
    
    # Filter models if specified
    if model_filter:
        models = [m for m in models if m.name in model_filter]
    
    results = []
    for model in models:
        logger.info("Evaluating %s in-domain...", model.name)
        in_domain_result = evaluate_model(
            f"{model.name}_in_domain",
            model.model,
            train_df_processed[common_features],  # using train as in-domain test
            train_df_processed["Attack Type"],
            model.cv_scores,
        )
        
        logger.info("Evaluating %s cross-domain (%s -> %s)...", model.name, train_config.name, test_config.name)
        cross_domain_result = evaluate_model(
            f"{model.name}_cross_domain",
            model.model,
            test_df_processed[common_features],
            test_df_processed["Attack Type"],
            model.cv_scores,
        )
        
        # Compute degradation metrics
        degradation = compute_degradation(in_domain_result, cross_domain_result)
        per_class_degradation = compute_per_class_degradation(in_domain_result, cross_domain_result)
        fpr_changes, fnr_changes = compute_fpr_fnr_changes(in_domain_result, cross_domain_result)
        
        result = CrossDatasetResult(
            train_dataset=train_config.name,
            test_dataset=test_config.name,
            model_name=model.name,
            in_domain_result=in_domain_result,
            cross_domain_result=cross_domain_result,
            degradation=degradation,
            per_class_degradation=per_class_degradation,
            fpr_change=fpr_changes,
            fnr_change=fnr_changes,
            feature_mapping=feature_mapping,
        )
        results.append(result)
        
        logger.info("Cross-domain degradation for %s: accuracy=%.2f%%, f1_macro=%.2f%%, mcc=%.2f%%",
                    model.name,
                    degradation.get("accuracy_pct", 0),
                    degradation.get("f1_macro_pct", 0),
                    degradation.get("mcc_pct", 0))
    
    return results


def run_bidirectional_experiment(
    dataset_a: str = "CIC-IDS2017",
    dataset_b: str = "UNSW-NB15",
    registry: 'DatasetRegistry' = None,
) -> dict:
    """Run bidirectional cross-dataset experiment (A->B and B->A)."""
    if registry is None:
        registry = dataset_registry
    
    logger.info("Running bidirectional cross-dataset experiment: %s <-> %s", dataset_a, dataset_b)
    
    # A -> B
    ab_results = run_cross_dataset_experiment(dataset_a, dataset_b, registry)
    
    # B -> A
    ba_results = run_cross_dataset_experiment(dataset_b, dataset_a, registry)
    
    return {
        f"{dataset_a}_to_{dataset_b}": [r.to_dict() for r in ab_results],
        f"{dataset_b}_to_{dataset_a}": [r.to_dict() for r in ba_results],
    }


def generate_generalization_report(results: dict) -> str:
    """Generate a human-readable generalization report."""
    lines = []
    lines.append("=" * 80)
    lines.append("CROSS-DATASET GENERALIZATION REPORT")
    lines.append("=" * 80)
    
    for direction, results_list in results.items():
        lines.append(f"\n--- {direction} ---")
        for r in results_list:
            d = r.get("degradation", {})
            lines.append(f"  Model: {r['model_name']}")
            lines.append(f"  In-domain accuracy: {r['in_domain']['accuracy']:.4f}")
            lines.append(f"  Cross-domain accuracy: {r['cross_domain']['accuracy']:.4f}")
            lines.append(f"  Accuracy degradation: {d.get('accuracy', 0):.4f} ({d.get('accuracy_pct', 0):.1f}%)")
            lines.append(f"  F1-macro degradation: {d.get('f1_macro', 0):.4f} ({d.get('f1_macro_pct', 0):.1f}%)")
            lines.append(f"  MCC degradation: {d.get('mcc', 0):.4f} ({d.get('mcc_pct', 0):.1f}%)")
            lines.append("")
    
    return "\n".join(lines)


if __name__ == "__main__":
    # Quick test
    print("Cross-dataset generalization module loaded successfully")
    print("Available datasets:", [d.name for d in dataset_registry.list_datasets()])