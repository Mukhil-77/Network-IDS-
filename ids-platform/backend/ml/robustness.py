"""
Model robustness testing for IDS.

Implements controlled perturbations to test model robustness against:
- Feature noise
- Missing feature values
- Feature scaling variations
- Traffic distribution changes
- Adversarial perturbations (within realistic constraints)

Research contribution: Model robustness testing and robustness gate for model promotion.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple
from typing import Union
import numpy as np
import warnings

from backend.utils.logger import get_logger

logger = get_logger(__name__)


class PerturbationType(Enum):
    """Types of perturbations for robustness testing."""
    GAUSSIAN_NOISE = "gaussian_noise"
    MISSING_FEATURES = "missing_features"
    SCALING_VARIATION = "scaling_variation"
    DISTRIBUTION_SHIFT = "distribution_shift"
    ADVERSARIAL_FGSM = "adversarial_fgsm"  # Fast Gradient Sign Method
    ADVERSARIAL_PGD = "adversarial_pgd"    # Projected Gradient Descent
    FEATURE_DROPOUT = "feature_dropout"
    VALUE_CLIPPING = "value_clipping"


@dataclass
class PerturbationConfig:
    """Configuration for a perturbation type."""
    perturbation_type: PerturbationType
    severity: float  # 0.0 to 1.0
    parameters: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        self.severity = max(0.0, min(1.0, self.severity))


@dataclass
class RobustnessResult:
    """Result of a robustness test."""
    perturbation_type: PerturbationType
    severity: float
    baseline_accuracy: float
    perturbed_accuracy: float
    accuracy_drop: float
    baseline_f1_macro: float
    perturbed_f1_macro: float
    f1_drop: float
    baseline_mcc: float
    perturbed_mcc: float
    mcc_drop: float
    per_class_degradation: Dict[str, float]
    prediction_changes: int  # Number of predictions that changed
    prediction_change_rate: float
    timestamp: datetime = field(default_factory=datetime.now)
    passed_gate: bool = False  # Whether it passes the robustness gate


class RobustnessTester:
    """
    Tests model robustness against various perturbations.
    
    Provides a robustness gate for model promotion - models must
    pass minimum robustness thresholds to be deployed.
    """
    
    def __init__(
        self,
        model: Any,
        X_test: np.ndarray,
        y_test: np.ndarray,
        feature_names: Optional[List[str]] = None,
        class_names: Optional[List[str]] = None,
        baseline_metrics: Optional[Dict[str, float]] = None,
    ):
        """
        Initialize robustness tester.
        
        Args:
            model: Fitted classifier with predict/predict_proba
            X_test: Test features (already preprocessed/PCA)
            y_test: Test labels
            feature_names: Feature names
            class_names: Class names
            baseline_metrics: Pre-computed baseline metrics
        """
        self.model = model
        self.X_test = X_test
        self.y_test = y_test
        self.feature_names = feature_names or [f"f{i}" for i in range(X_test.shape[1])]
        self.class_names = class_names or []
        self.baseline_metrics = baseline_metrics or {}
        
        # Compute baseline if not provided
        if not self.baseline_metrics:
            self.baseline_metrics = self._compute_baseline()
    
    def _compute_baseline(self) -> Dict[str, float]:
        """Compute baseline metrics on clean test data."""
        from sklearn.metrics import accuracy_score, f1_score, matthews_corrcoef
        
        y_pred = self.model.predict(self.X_test)
        
        return {
            "accuracy": float(accuracy_score(self.y_test, y_pred)),
            "f1_macro": float(f1_score(self.y_test, y_pred, average='macro', zero_division=0)),
            "mcc": float(np.corrcoef(self.y_test, y_pred)[0,1]) if len(np.unique(self.y_test)) > 1 else 0.0,
        }
    
    def apply_gaussian_noise(self, X: np.ndarray, severity: float) -> np.ndarray:
        """Add Gaussian noise to features."""
        noise_std = severity * np.std(X, axis=0)
        noise = np.random.normal(0, noise_std, X.shape)
        return X + noise
    
    def apply_missing_features(self, X: np.ndarray, severity: float, 
                               missing_rate: Optional[float] = None) -> np.ndarray:
        """Randomly set features to zero (simulate missing features)."""
        rate = missing_rate or severity
        mask = np.random.random(X.shape) > rate
        return X * mask
    
    def apply_scaling_variation(self, X: np.ndarray, severity: float) -> np.ndarray:
        """Apply random scaling to features."""
        scale_factors = 1.0 + severity * (np.random.random(X.shape[1]) - 0.5) * 2
        return X * scale_factors
    
    def apply_distribution_shift(self, X: np.ndarray, severity: float) -> np.ndarray:
        """Shift feature distributions."""
        shift_magnitude = severity * np.std(X, axis=0)
        shift = np.random.normal(0, shift_magnitude, X.shape[1])
        return X + shift
    
    def apply_feature_dropout(self, X: np.ndarray, severity: float) -> np.ndarray:
        """Randomly zero out entire features (simulate sensor failure)."""
        n_features = X.shape[1]
        n_drop = int(severity * n_features)
        drop_indices = np.random.choice(n_features, n_drop, replace=False)
        X_perturbed = X.copy()
        X_perturbed[:, drop_indices] = 0
        return X_perturbed
    
    def apply_value_clipping(self, X: np.ndarray, severity: float) -> np.ndarray:
        """Clip extreme values to simulate sensor saturation."""
        clip_percentile = 99 - severity * 50  # 99% to 49%
        lower = np.percentile(X, 100 - clip_percentile, axis=0)
        upper = np.percentile(X, clip_percentile, axis=0)
        return np.clip(X, lower, upper)
    
    def apply_adversarial_fgsm(self, X: np.ndarray, y: np.ndarray, 
                               severity: float, eps: Optional[float] = None) -> np.ndarray:
        """
        Fast Gradient Sign Method (FGSM) adversarial attack.
        
        Note: Requires model to have gradient computation (not available for RF/DT).
        For tree-based models, this is a placeholder.
        """
        # For tree-based models, we can't compute gradients directly
        # Use a surrogate model or approximate with noise
        logger.warning("FGSM not directly applicable to tree models, using noise approximation")
        return self.apply_gaussian_noise(X, severity)
    
    def apply_adversarial_pgd(self, X: np.ndarray, y: np.ndarray,
                              severity: float, eps: float = 0.3, 
                              alpha: float = 0.01, steps: int = 10) -> np.ndarray:
        """
        Projected Gradient Descent (PGD) adversarial attack.
        
        Note: Requires gradient computation (not available for RF/DT).
        """
        logger.warning("PGD not directly applicable to tree models, using noise approximation")
        return self.apply_gaussian_noise(X, severity)
    
    def apply_perturbation(self, X: np.ndarray, y: np.ndarray, 
                          config: PerturbationConfig) -> np.ndarray:
        """Apply a perturbation based on config."""
        if config.perturbation_type == PerturbationType.GAUSSIAN_NOISE:
            return self.apply_gaussian_noise(X, config.severity)
        elif config.perturbation_type == PerturbationType.MISSING_FEATURES:
            return self.apply_missing_features(X, config.severity)
        elif config.perturbation_type == PerturbationType.SCALING_VARIATION:
            return self.apply_scaling_variation(X, config.severity)
        elif config.perturbation_type == PerturbationType.DISTRIBUTION_SHIFT:
            return self.apply_distribution_shift(X, config.severity)
        elif config.perturbation_type == PerturbationType.FEATURE_DROPOUT:
            return self.apply_feature_dropout(X, config.severity)
        elif config.perturbation_type == PerturbationType.VALUE_CLIPPING:
            return self.apply_value_clipping(X, config.severity)
        elif config.perturbation_type == PerturbationType.ADVERSARIAL_FGSM:
            return self.apply_adversarial_fgsm(X, self.y_test, config.severity)
        elif config.perturbation_type == PerturbationType.ADVERSARIAL_PGD:
            return self.apply_adversarial_pgd(X, self.y_test, config.severity)
        else:
            raise ValueError(f"Unknown perturbation type: {config.perturbation_type}")
    
    def test_perturbation(self, config: PerturbationConfig) -> RobustnessResult:
        """Test a single perturbation configuration."""
        # Apply perturbation
        X_perturbed = self.apply_perturbation(self.X_test, self.y_test, config)
        
        # Get predictions
        y_pred_baseline = self.model.predict(self.X_test)
        y_pred_perturbed = self.model.predict(X_perturbed)
        
        # Compute metrics
        from sklearn.metrics import accuracy_score, f1_score, matthews_corrcoef
        
        baseline_acc = accuracy_score(self.y_test, y_pred_baseline)
        perturbed_acc = accuracy_score(self.y_test, y_pred_perturbed)
        
        baseline_f1 = f1_score(self.y_test, y_pred_baseline, average='macro', zero_division=0)
        perturbed_f1 = f1_score(self.y_test, y_pred_perturbed, average='macro', zero_division=0)
        
        baseline_mcc = np.corrcoef(self.y_test, y_pred_baseline)[0,1] if len(np.unique(self.y_test)) > 1 else 0.0
        perturbed_mcc = np.corrcoef(self.y_test, y_pred_perturbed)[0,1] if len(np.unique(self.y_test)) > 1 else 0.0
        
        # Per-class degradation
        from sklearn.metrics import f1_score
        classes = np.unique(self.y_test)
        per_class_degradation = {}
        for cls in classes:
            mask = (self.y_test == cls)
            if mask.sum() > 0:
                baseline_f1_cls = f1_score(self.y_test[mask], y_pred_baseline[mask], average='binary', zero_division=0)
                perturbed_f1_cls = f1_score(self.y_test[mask], y_pred_perturbed[mask], average='binary', zero_division=0)
                per_class_degradation[str(cls)] = baseline_f1_cls - perturbed_f1_cls
        
        # Prediction changes
        prediction_changes = int(np.sum(y_pred_baseline != y_pred_perturbed))
        prediction_change_rate = prediction_changes / len(y_pred_baseline)
        
        accuracy_drop = baseline_acc - perturbed_acc
        f1_drop = baseline_f1 - perturbed_f1
        mcc_drop = baseline_mcc - perturbed_mcc
        
        return RobustnessResult(
            perturbation_type=config.perturbation_type,
            severity=config.severity,
            baseline_accuracy=baseline_acc,
            perturbed_accuracy=perturbed_acc,
            accuracy_drop=accuracy_drop,
            baseline_f1_macro=baseline_f1,
            perturbed_f1_macro=perturbed_f1,
            f1_drop=f1_drop,
            baseline_mcc=baseline_mcc,
            perturbed_mcc=perturbed_mcc,
            mcc_drop=mcc_drop,
            per_class_degradation=per_class_degradation,
            prediction_changes=prediction_changes,
            prediction_change_rate=prediction_change_rate,
        )
    
    def run_robustness_suite(
        self, 
        severities: List[float] = None,
        perturbation_types: List[PerturbationType] = None,
    ) -> List[RobustnessResult]:
        """
        Run a full robustness test suite.
        
        Args:
            severities: List of severity levels to test (0.0 to 1.0)
            perturbation_types: Types of perturbations to test
            
        Returns:
            List of RobustnessResult for each perturbation/severity combination
        """
        if severities is None:
            severities = [0.05, 0.1, 0.2, 0.3, 0.5]
        
        if perturbation_types is None:
            perturbation_types = [
                PerturbationType.GAUSSIAN_NOISE,
                PerturbationType.MISSING_FEATURES,
                PerturbationType.SCALING_VARIATION,
                PerturbationType.DISTRIBUTION_SHIFT,
                PerturbationType.FEATURE_DROPOUT,
                PerturbationType.VALUE_CLIPPING,
            ]
        
        results = []
        for ptype in perturbation_types:
            for severity in severities:
                config = PerturbationConfig(perturbation_type=ptype, severity=severity)
                result = self.test_perturbation(config)
                
                # Check if passes robustness gate
                # Gate: accuracy drop < 5%, F1 drop < 10%
                result.passed_gate = (
                    result.accuracy_drop < 0.05 and 
                    result.f1_drop < 0.10
                )
                
                results.append(result)
                logger.info(
                    f"{config.perturbation_type.value} (severity={severity:.2f}): "
                    f"acc_drop={result.accuracy_drop:.4f}, f1_drop={result.f1_drop:.4f}, "
                    f"gate={'PASS' if result.passed_gate else 'FAIL'}"
                )
        
        return results
    
    def generate_robustness_report(self, results: List[RobustnessResult]) -> Dict[str, Any]:
        """Generate a summary report from robustness results."""
        if not results:
            return {"status": "no_results"}
        
        # Group by perturbation type
        by_type = {}
        for r in results:
            if r.perturbation_type not in by_type:
                by_type[r.perturbation_type] = []
            by_type[r.perturbation_type].append(r)
        
        summary = {
            "total_tests": len(results),
            "passed": sum(1 for r in results if r.passed_gate),
            "failed": sum(1 for r in results if not r.passed_gate),
            "by_type": {},
            "worst_case": None,
            "recommendations": [],
        }
        
        worst_drop = 0
        worst_result = None
        
        for ptype, results_list in by_type.items():
            type_summary = {
                "tests": len(results_list),
                "passed": sum(1 for r in results_list if r.passed_gate),
                "max_accuracy_drop": max(r.accuracy_drop for r in results_list),
                "max_f1_drop": max(r.f1_drop for r in results_list),
                "max_mcc_drop": max(r.mcc_drop for r in results_list),
                "severities_tested": [r.severity for r in results_list],
            }
            summary["by_type"][ptype.value] = type_summary
            
            # Track worst case
            for r in results_list:
                if r.accuracy_drop > worst_drop:
                    worst_drop = r.accuracy_drop
                    worst_result = r
        
        if worst_result:
            summary["worst_case"] = {
                "perturbation": worst_result.perturbation_type.value,
                "severity": worst_result.severity,
                "accuracy_drop": worst_result.accuracy_drop,
                "f1_drop": worst_result.f1_drop,
            }
        
        # Generate recommendations
        if summary["failed"] > 0:
            summary["recommendations"].append(
                f"{summary['failed']} robustness tests failed the gate. "
                "Consider: data augmentation, robust training, or feature selection."
            )
        if any(r.f1_drop > 0.15 for r in results):
            summary["recommendations"].append(
                "Some perturbations cause >15% F1 drop. "
                "Investigate feature sensitivity and consider robust training."
            )
        if any(r.prediction_change_rate > 0.2 for r in results):
            summary["recommendations"].append(
                "High prediction change rate (>20%) under perturbation. "
                "Model predictions are unstable. Consider ensemble or regularization."
            )
        
        return summary
    
    def check_robustness_gate(self, results: List[RobustnessResult]) -> bool:
        """Check if all results pass the robustness gate."""
        return all(r.passed_gate for r in results)
    
    def generate_gate_report(self, results: List[RobustnessResult]) -> str:
        """Generate a text report for the robustness gate."""
        report = []
        report.append("=" * 60)
        report.append("ROBUSTNESS GATE REPORT")
        report.append("=" * 60)
        report.append(f"Total tests: {len(results)}")
        report.append(f"Passed: {sum(1 for r in results if r.passed_gate)}")
        report.append(f"Failed: {sum(1 for r in results if not r.passed_gate)}")
        report.append("")
        
        for r in results:
            status = "PASS" if r.passed_gate else "FAIL"
            report.append(
                f"  {r.perturbation_type.value} (severity={r.severity:.2f}): "
                f"acc_drop={r.accuracy_drop:.4f}, f1_drop={r.f1_drop:.4f}, "
                f"pred_change={r.prediction_change_rate:.2%} [{status}]"
            )
        
        report.append("")
        if all(r.passed_gate for r in results):
            report.append("GATE STATUS: PASS - Model meets robustness requirements")
        else:
            report.append("GATE STATUS: FAIL - Model does not meet robustness requirements")
            report.append("Recommendation: Do not deploy until robustness improved")
        
        return "\n".join(report)


# Robustness gate for model promotion
class RobustnessGate:
    """
    Gate that must be passed before model promotion to production.
    
    Configurable thresholds for different perturbation types.
    """
    
    def __init__(
        self,
        max_accuracy_drop: float = 0.05,
        max_f1_drop: float = 0.10,
        max_mcc_drop: float = 0.10,
        max_prediction_change_rate: float = 0.20,
        required_severities: List[float] = None,
    ):
        self.max_accuracy_drop = max_accuracy_drop
        self.max_f1_drop = max_f1_drop
        self.max_mcc_drop = max_mcc_drop
        self.max_prediction_change_rate = max_prediction_change_rate
        self.required_severities = required_severities or [0.05, 0.1, 0.2]
    
    def evaluate(self, results: List[RobustnessResult]) -> Tuple[bool, Dict[str, Any]]:
        """Evaluate results against gate thresholds."""
        violations = []
        
        for r in results:
            if r.accuracy_drop > self.max_accuracy_drop:
                violations.append(
                    f"{r.perturbation_type.value} (severity={r.severity}): "
                    f"accuracy drop {r.accuracy_drop:.4f} > {self.max_accuracy_drop}"
                )
            if r.f1_drop > self.max_f1_drop:
                violations.append(
                    f"{r.perturbation_type.value} (severity={r.severity}): "
                    f"F1 drop {r.f1_drop:.4f} > {self.max_f1_drop}"
                )
            if r.mcc_drop > self.max_mcc_drop:
                violations.append(
                    f"{r.perturbation_type.value} (severity={r.severity}): "
                    f"MCC drop {r.mcc_drop:.4f} > {self.max_mcc_drop}"
                )
            if r.prediction_change_rate > self.max_prediction_change_rate:
                violations.append(
                    f"{r.perturbation_type.value} (severity={r.severity}): "
                    f"prediction change rate {r.prediction_change_rate:.2%} > {self.max_prediction_change_rate:.0%}"
                )
        
        passed = len(violations) == 0
        
        return passed, {
            "passed": passed,
            "violations": violations,
            "total_tests": len(results),
            "thresholds": {
                "max_accuracy_drop": self.max_accuracy_drop,
                "max_f1_drop": self.max_f1_drop,
                "max_mcc_drop": self.max_mcc_drop,
                "max_prediction_change_rate": self.max_prediction_change_rate,
            },
        }


# Example usage:
#
# from backend.ml.robustness import RobustnessTester, RobustnessGate, PerturbationType
# from sklearn.ensemble import RandomForestClassifier
#
# # Assume model, X_test, y_test are available
# tester = RobustnessTester(model, X_test, y_test, feature_names, class_names)
#
# # Run robustness suite
# results = tester.run_robustness_suite(
#     severities=[0.05, 0.1, 0.2, 0.3],
#     perturbation_types=[
#         PerturbationType.GAUSSIAN_NOISE,
#         PerturbationType.MISSING_FEATURES,
#         PerturbationType.SCALING_VARIATION,
#         PerturbationType.DISTRIBUTION_SHIFT,
#     ]
# )
#
# # Check gate
# gate = RobustnessGate(max_accuracy_drop=0.05, max_f1_drop=0.10)
# passed, report = gate.evaluate(results)
#
# print(tester.generate_gate_report(results))
# print(f"Gate: {'PASS' if passed else 'FAIL'}")