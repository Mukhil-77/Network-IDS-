"""
Model Robustness Testing

Tests model robustness against various perturbations:
- Gaussian noise injection
- Feature scaling variations
- Missing feature values
- Adversarial perturbations (FGSM-style)
- Distribution shift simulation
- Out-of-distribution detection

Reports:
- Baseline performance
- Perturbed performance
- Performance drop percentage
- Per-class robustness
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional, Callable, Union
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, matthews_corrcoef

from backend.ml.evaluation import EvaluationResult, evaluate_model
from backend.ml.training import prepare_multiclass_dataset, train_all_multiclass_models
from backend.ml.evaluation import compute_per_class_fpr_fnr
from backend.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class RobustnessResult:
    """Results from a robustness test."""
    test_name: str
    perturbation_type: str
    perturbation_params: dict
    baseline_metrics: dict
    perturbed_metrics: dict
    performance_drop: dict
    per_class_drop: dict[str, dict[str, float]]
    passed: bool  # Whether drop is within acceptable threshold


@dataclass
class RobustnessReport:
    """Complete robustness evaluation report."""
    model_name: str
    timestamp: str
    dataset_info: dict
    test_results: list
    overall_robustness: float  # 0-1, higher = more robust
    critical_weaknesses: list[str]
    recommendations: list[str]


class RobustnessTester:
    """
    Tests model robustness against various perturbations.
    """
    
    def __init__(
        self,
        model: Any,
        X_test: pd.DataFrame,
        y_test: pd.Series,
        class_names: list[str],
        acceptable_drop: float = 0.1,  # 10% acceptable performance drop
    ):
        self.model = model
        self.X_test = X_test
        self.y_test = y_test
        self.class_names = class_names
        self.acceptable_drop = acceptable_drop
        
        # Baseline predictions
        self.y_pred_baseline = model.predict(X_test)
        self.y_prob_baseline = model.predict_proba(X_test) if hasattr(model, "predict_proba") else None
        
        # Baseline metrics
        self.baseline_result = evaluate_model(
            "baseline", model, X_test, y_test
        )
        self.baseline_metrics = self._extract_metrics(self.baseline_result)
    
    def _extract_metrics(self, result: 'EvaluationResult') -> dict:
        """Extract metrics from evaluation result."""
        return {
            "accuracy": result.accuracy,
            "f1_macro": result.f1_macro,
            "f1_weighted": result.f1_weighted,
            "precision_macro": result.precision_macro,
            "recall_macro": result.recall_macro,
            "mcc": result.mcc,
            "per_class_precision": {k: v for k, v in result.classification_report.items() if k in self.class_names},
            "per_class_recall": {k: v for k, v in result.classification_report.items() if k in self.class_names},
            "per_class_f1": {k: v for k, v in result.classification_report.items() if k in self.class_names},
        }
    
    def test_gaussian_noise(self, noise_levels: list[float] = None) -> list[RobustnessResult]:
        """Test robustness to Gaussian noise injection."""
        if noise_levels is None:
            noise_levels = [0.01, 0.05, 0.1, 0.2, 0.3]
        
        results = []
        for noise_std in noise_levels:
            # Add Gaussian noise
            noise = np.random.normal(0, noise_std, self.X_test.shape)
            X_noisy = self.X_test + noise
            
            # Evaluate
            result = self._evaluate_perturbed(f"gaussian_noise_std_{noise_std}", X_noisy, {"noise_std": noise_std})
            results.append(result)
        
        return results
    
    def test_feature_scaling(self, scale_factors: list[float] = None) -> list[RobustnessResult]:
        """Test robustness to feature scaling variations."""
        if scale_factors is None:
            scale_factors = [0.5, 0.8, 1.2, 1.5, 2.0]
        
        results = []
        for scale in scale_factors:
            X_scaled = self.X_test * scale
            result = self._evaluate_perturbed(f"feature_scale_{scale}", X_scaled, {"scale_factor": scale})
            results.append(result)
        
        return results
    
    def test_missing_features(self, missing_ratios: list[float] = None) -> list[RobustnessResult]:
        """Test robustness to missing features (set to 0 or mean)."""
        if missing_ratios is None:
            missing_ratios = [0.05, 0.1, 0.2, 0.3]
        
        results = []
        for ratio in missing_ratios:
            X_missing = self.X_test.copy()
            n_features = X_missing.shape[1]
            n_missing = int(n_features * ratio)
            
            # Randomly select features to zero out
            for i in range(len(X_missing)):
                missing_idx = np.random.choice(X_missing.shape[1], n_missing, replace=False)
                X_missing.iloc[i, missing_idx] = 0
            
            result = self._evaluate_perturbed(f"missing_features_{ratio}", X_missing, {"missing_ratio": ratio})
            results.append(result)
        
        return results
    
    def test_adversarial_fgsm(self, epsilons: list[float] = None) -> list[RobustnessResult]:
        """
        Test against Fast Gradient Sign Method (FGSM) adversarial attacks.
        Note: This is a simplified version for models without gradient access.
        Uses random perturbations in the direction of feature importance.
        """
        if epsilons is None:
            epsilons = [0.01, 0.05, 0.1, 0.2]
        
        # Estimate feature importance using permutation importance
        if not hasattr(self, '_feature_importance'):
            self._feature_importance = self._estimate_feature_importance()
        
        results = []
        for eps in epsilons:
            X_adv = self.X_test.copy()
            
            # Perturb most important features
            for i, feat in enumerate(self.X_test.columns):
                importance = self._feature_importance.get(feat, 1.0)
                # Perturb in direction that would flip prediction
                perturbation = eps * importance * np.random.choice([-1, 1])
                self.X_test[feat] += perturbation
            
            X_adv = self.X_test
            result = self._evaluate_perturbed(f"fgsm_eps_{eps}", X_adv, {"epsilon": eps})
            results.append(result)
        
        return results
    
    def _estimate_feature_importance(self) -> dict[str, float]:
        """Estimate feature importance using permutation."""
        baseline_acc = accuracy_score(self.y_test, self.y_pred_baseline)
        importances = {}
        
        for feat in self.X_test.columns:
            X_permuted = self.X_test.copy()
            X_permuted[feat] = np.random.permutation(X_permuted[feat].values)
            y_pred_perm = self.model.predict(X_permuted)
            acc = accuracy_score(self.y_test, y_pred_perm)
            importances[feat] = baseline_acc - acc  # Drop in accuracy
        
        # Normalize
        total = sum(importances.values())
        if total > 0:
            importances = {k: v/total for k, v in importances.items()}
        
        return importances
    
    def test_distribution_shift(self, shift_factors: list[float] = None) -> list[RobustnessResult]:
        """Test robustness to distribution shift (covariate shift)."""
        if shift_factors is None:
            shift_factors = [0.5, 0.8, 1.2, 1.5, 2.0]
        
        results = []
        for shift in shift_factors:
            # Shift feature distributions
            X_shifted = self.X_test.copy()
            for feat in self.X_test.columns:
                mean = self.X_test[feat].mean()
                std = self.X_test[feat].std()
                X_shifted[feat] = (X_shifted[feat] - mean) * shift + mean
            
            result = self._evaluate_perturbed(f"dist_shift_{shift}", X_shifted, {"shift_factor": shift})
            results.append(result)
        
        return results
    
    def test_out_of_distribution(self, ood_factors: list[float] = None) -> list[RobustnessResult]:
        """Test detection of out-of-distribution samples."""
        if ood_factors is None:
            ood_factors = [2.0, 3.0, 5.0]
        
        results = []
        for factor in ood_factors:
            # Generate OOD samples (far from training distribution)
            X_ood = self.X_test.copy()
            for feat in self.X_test.columns:
                mean = self.X_test[feat].mean()
                std = self.X_test[feat].std()
                # Shift far outside training distribution
                X_ood[feat] = X_ood[feat] + factor * std * np.random.randn(len(X_ood))
            
            # Evaluate (expect low confidence predictions)
            result = self._evaluate_perturbed(f"ood_factor_{factor}", X_ood, {"ood_factor": factor})
            results.append(result)
        
        return results
    
    def _evaluate_perturbed(
        self, 
        test_name: str, 
        X_perturbed: pd.DataFrame, 
        params: dict
    ) -> RobustnessResult:
        """Evaluate model on perturbed data."""
        # Get predictions
        y_pred = self.model.predict(X_perturbed)
        y_prob = self.model.predict_proba(X_perturbed) if hasattr(self.model, "predict_proba") else None
        
        # Evaluate
        perturbed_result = evaluate_model(
            f"{test_name}", self.model, X_perturbed, self.y_test
        )
        perturbed_metrics = self._extract_metrics(perturbed_result)
        
        # Compute performance drops
        performance_drop = {
            "accuracy": self.baseline_metrics["accuracy"] - perturbed_metrics["accuracy"],
            "f1_macro": self.baseline_metrics["f1_macro"] - perturbed_metrics["f1_macro"],
            "f1_weighted": self.baseline_metrics["f1_weighted"] - perturbed_metrics["f1_weighted"],
            "precision_macro": self.baseline_metrics["precision_macro"] - perturbed_metrics["precision_macro"],
            "recall_macro": self.baseline_metrics["recall_macro"] - perturbed_metrics["recall_macro"],
            "mcc": self.baseline_metrics["mcc"] - perturbed_metrics["mcc"],
        }
        
        # Per-class drops
        per_class_drop = {}
        for cls in self.class_names:
            if cls in self.baseline_result.classification_report and cls in perturbed_result.classification_report:
                base = self.baseline_result.classification_report[cls]
                pert = perturbed_result.classification_report[cls]
                per_class_drop[cls] = {
                    "precision": base.get("precision", 0) - pert.get("precision", 0),
                    "recall": base.get("recall", 0) - pert.get("recall", 0),
                    "f1": base.get("f1-score", 0) - pert.get("f1-score", 0),
                }
        
        # Check if passes threshold
        max_drop = max(abs(v) for v in performance_drop.values())
        passed = max_drop <= self.acceptable_drop
        
        return RobustnessResult(
            test_name=test_name,
            perturbation_type=test_name.split("_")[0],
            perturbation_params=params,
            baseline_metrics=self.baseline_metrics,
            perturbed_metrics=perturbed_metrics,
            performance_drop=performance_drop,
            per_class_drop=per_class_drop,
            passed=passed,
        )
    
    def run_all_tests(self) -> dict[str, list[RobustnessResult]]:
        """Run all robustness tests."""
        logger.info("Starting comprehensive robustness testing...")
        
        all_results = {}
        all_results["gaussian_noise"] = self.test_gaussian_noise()
        all_results["feature_scaling"] = self.test_feature_scaling()
        all_results["missing_features"] = self.test_missing_features()
        all_results["distribution_shift"] = self.test_distribution_shift()
        all_results["out_of_distribution"] = self.test_out_of_distribution()
        
        # FGSM test (may be slow)
        try:
            all_results["fgsm"] = self.test_adversarial_fgsm()
        except Exception as e:
            logger.warning(f"FGSM test failed: {e}")
            all_results["fgsm"] = []
        
        return all_results
    
    def generate_report(self, all_results: dict[str, list[RobustnessResult]]) -> RobustnessReport:
        """Generate comprehensive robustness report."""
        # Flatten all results
        all_tests = []
        for category, results in all_results.items():
            for r in results:
                all_tests.append(r)
        
        # Compute overall robustness (1 - average max drop)
        if all_tests:
            avg_max_drop = np.mean([max(abs(v) for v in r.performance_drop.values()) for r in all_tests])
            overall_robustness = max(0, 1 - avg_drop)
        else:
            overall_robustness = 1.0
        
        # Identify critical weaknesses
        weaknesses = []
        for r in all_tests:
            if not r.passed:
                weaknesses.append(f"{r.test_name}: {max(abs(v) for v in r.performance_drop.values()):.1%} max drop")
        
        # Recommendations
        recommendations = [
            "Consider adversarial training for improved robustness",
            "Add feature denoising preprocessing",
            "Implement input validation and range checking",
            "Monitor prediction confidence distributions in production",
            "Set up drift detection for feature distributions",
        ]
        
        return RobustnessReport(
            model_name=getattr(self.model, '__class__.__name__', 'unknown'),
            timestamp=datetime.now(timezone.utc).isoformat(),
            dataset_info={
                "test_samples": len(self.X_test),
                "features": len(self.X_test.columns),
                "classes": len(self.class_names),
            },
            test_results=[r for results in all_results.values() for r in results],
            overall_robustness=overall_robustness,
            critical_weaknesses=weaknesses,
            recommendations=recommendations,
        )


def run_robustness_evaluation(
    model: Any,
    X_test: pd.DataFrame,
    y_test: pd.Series,
    class_names: list[str],
) -> RobustnessReport:
    """
    Run complete robustness evaluation and generate report.
    
    Returns:
        RobustnessReport with all test results
    """
    tester = RobustnessTester(model, X_test, y_test, class_names)
    all_results = tester.run_all_tests()
    report = tester.generate_report(all_results)
    return report


if __name__ == "__main__":
    print("Robustness testing module loaded successfully")