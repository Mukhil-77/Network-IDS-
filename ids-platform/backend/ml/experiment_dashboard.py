"""
Research experiment dashboard and evaluation framework.

Provides BASELINE vs IMPROVED comparison with charts/tables for:
- Accuracy, Macro-F1, Precision, Recall, FPR, FNR, PR-AUC, MCC
- Latency, Throughput, Memory
- Unknown detection, Cross-dataset performance

Research contribution: Experimental proof with reproducible experiments.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import json
import numpy as np
import pandas as pd

from backend.utils.logger import get_logger

logger = get_logger(__name__)


class ExperimentType(Enum):
    """Types of research experiments."""
    LEAKAGE_TEST = "leakage_test"                    # Current vs leakage-free SMOTE
    IMBALANCE = "imbalance"                          # Current balancing vs train-only
    FALSE_ALARMS = "false_alarms"                    # Current threshold vs calibrated
    GENERALIZATION = "generalization"                # CIC-only vs cross-dataset
    ZERO_DAY = "zero_day"                            # Closed-set vs leave-one-out
    TEMPORAL = "temporal"                            # Random split vs time-aware
    EXPLAINABILITY = "explainability"                # No explanation vs XAI
    DEPLOYMENT = "deployment"                        # Classification latency vs sustained test
    RESPONSE = "response"                            # Simulation vs risk-gated verified
    RECOVERY = "recovery"                            # Action result only vs verification+rollback
    ROBUSTNESS = "robustness"                        # Baseline vs perturbed inputs


@dataclass
class ExperimentConfig:
    """Configuration for a research experiment."""
    experiment_type: ExperimentType
    name: str
    description: str
    baseline_config: Dict[str, Any]
    improved_config: Dict[str, Any]
    datasets: List[str]
    metrics: List[str]
    random_seeds: List[int] = field(default_factory=lambda: [42, 123, 456, 789, 999])
    n_runs: int = 5


@dataclass
class ExperimentResult:
    """Results from a single experiment run."""
    experiment_type: ExperimentType
    run_id: str
    seed: int
    baseline_metrics: Dict[str, float]
    improved_metrics: Dict[str, float]
    differences: Dict[str, float]  # improved - baseline
    p_values: Dict[str, float] = field(default_factory=dict)
    effect_sizes: Dict[str, float] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    notes: str = ""


class ExperimentRunner:
    """
    Runs research experiments and collects results.
    
    Provides reproducible experiments with fixed seeds and statistical testing.
    """
    
    def __init__(self, output_dir: str = "experiment_results"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.experiments: List[ExperimentConfig] = []
        self.results: List[ExperimentResult] = []
    
    def add_experiment(self, config: ExperimentConfig):
        """Add an experiment to the suite."""
        self.experiments.append(config)
        logger.info(f"Added experiment: {config.name} ({config.experiment_type.value})")
    
    def run_experiment(self, config: ExperimentConfig, 
                      baseline_fn: Callable,
                      improved_fn: Callable) -> List[ExperimentResult]:
        """
        Run a single experiment with multiple seeds.
        
        Args:
            config: Experiment configuration
            baseline_fn: Function that runs baseline and returns metrics dict
            improved_fn: Function that runs improved system and returns metrics dict
            
        Returns:
            List of ExperimentResult for each seed
        """
        results = []
        
        for seed in config.random_seeds[:config.n_runs]:
            logger.info(f"Running {config.name} with seed {seed}")
            
            # Set seeds for reproducibility
            np.random.seed(seed)
            
            # Run baseline
            baseline_metrics = baseline_fn(seed=seed)
            
            # Run improved
            improved_metrics = improved_fn(seed=seed)
            
            # Compute differences
            differences = {}
            for key in baseline_metrics:
                if key in improved_metrics:
                    differences[key] = improved_metrics[key] - baseline_metrics[key]
            
            # Statistical testing (simplified - would need multiple runs for real p-values)
            p_values = {}
            effect_sizes = {}
            
            result = ExperimentResult(
                experiment_type=config.experiment_type,
                run_id=f"{config.experiment_type.value}_{seed}",
                seed=seed,
                baseline_metrics=baseline_metrics,
                improved_metrics=improved_metrics,
                differences=differences,
                p_values=p_values,
                effect_sizes=effect_sizes,
            )
            
            results.append(result)
            self.results.append(result)
        
        return results
    
    def run_all_experiments(
        self,
        baseline_fns: Dict[ExperimentType, Callable],
        improved_fns: Dict[ExperimentType, Callable],
    ) -> Dict[ExperimentType, List[ExperimentResult]]:
        """Run all configured experiments."""
        all_results = {}
        
        for config in self.experiments:
            if config.experiment_type not in baseline_fns or config.experiment_type not in improved_fns:
                logger.warning(f"Missing functions for {config.experiment_type.value}, skipping")
                continue
            
            results = self.run_experiment(
                config, 
                baseline_fns[config.experiment_type],
                improved_fns[config.experiment_type],
            )
            all_results[config.experiment_type] = results
        
        return all_results
    
    def generate_comparison_report(self, results: Dict[ExperimentType, List[ExperimentResult]]) -> str:
        """Generate a comprehensive comparison report."""
        report = []
        report.append("=" * 80)
        report.append("RESEARCH EXPERIMENT COMPARISON REPORT")
        report.append("=" * 80)
        report.append(f"Generated: {datetime.now().isoformat()}")
        report.append(f"Total Experiments: {len(results)}")
        report.append("")
        
        for exp_type, exp_results in results.items():
            if not exp_results:
                continue
                
            report.append(f"\n{'='*80}")
            report.append(f"EXPERIMENT: {exp_type.value.upper()}")
            report.append(f"{'='*80}")
            
            # Aggregate across seeds
            baseline_agg = self._aggregate_metrics([r.baseline_metrics for r in exp_results])
            improved_agg = self._aggregate_metrics([r.improved_metrics for r in exp_results])
            diff_agg = {}
            for key in baseline_agg:
                if key in improved_agg:
                    diff_agg[key] = improved_agg[key] - baseline_agg[key]
            
            report.append(f"  Runs: {len(exp_results)}")
            report.append(f"  Seeds: {[r.seed for r in exp_results]}")
            report.append("")
            
            # Key metrics table
            key_metrics = [
                "accuracy", "f1_macro", "f1_weighted", "mcc", 
                "precision_macro", "recall_macro", "fpr_macro", "fnr_macro",
                "pr_auc", "roc_auc_ovr", "roc_auc_ovo",
                "latency_p50_ms", "latency_p95_ms", "throughput_fps",
                "cpu_percent", "memory_mb",
            ]
            
            report.append("  METRIC COMPARISON (mean ± std):")
            report.append(f"  {'Metric':<30} {'Baseline':>15} {'Improved':>15} {'Diff':>10} {'% Change':>10}")
            report.append(f"  {'-'*70}")
            
            for metric in key_metrics:
                if metric in baseline_agg:
                    b_mean = baseline_agg[metric].get('mean', 0)
                    b_std = baseline_agg[metric].get('std', 0)
                    i_mean = improved_agg.get(metric, {}).get('mean', 0)
                    i_std = improved_agg.get(metric, {}).get('std', 0)
                    diff = i_mean - b_mean
                    pct = (diff / b_mean * 100) if b_mean != 0 else 0
                    report.append(
                        f"  {metric:<30} {b_mean:>10.4f}±{b_std:<4.4f} {i_mean:>10.4f}±{i_std:<4.4f} {diff:>+10.4f} {pct:>+9.1f}%"
                    )
            
            report.append("")
        
        return "\n".join(report)
    
    def _aggregate_metrics(self, metrics_list: List[Dict[str, float]]) -> Dict[str, Dict[str, float]]:
        """Aggregate metrics across runs (mean, std)."""
        if not metrics_list:
            return {}
        
        all_keys = set()
        for m in metrics_list:
            all_keys.update(m.keys())
        
        agg = {}
        for key in all_keys:
            values = [m.get(key, 0) for m in metrics_list if key in m]
            if values:
                agg[key] = {
                    "mean": np.mean(values),
                    "std": np.std(values) if len(values) > 1 else 0,
                    "min": np.min(values),
                    "max": np.max(values),
                    "values": values,
                }
        return agg
    
    def save_results(self, filename: str = "experiment_results.json"):
        """Save all results to JSON."""
        data = {
            "timestamp": datetime.now().isoformat(),
            "experiments": [
                {
                    "type": exp.experiment_type.value,
                    "name": exp.name,
                    "description": exp.description,
                }
                for exp in self.experiments
            ],
            "results": [
                {
                    "experiment_type": r.experiment_type.value,
                    "run_id": r.run_id,
                    "seed": r.seed,
                    "baseline_metrics": r.baseline_metrics,
                    "improved_metrics": r.improved_metrics,
                    "differences": r.differences,
                    "p_values": r.p_values,
                    "effect_sizes": r.effect_sizes,
                    "timestamp": r.timestamp.isoformat(),
                    "notes": r.notes,
                }
                for r in self.results
            ],
        }
        
        filepath = self.output_dir / filename
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        
        logger.info(f"Saved results to {filepath}")
        return str(filepath)
    
    def load_results(self, filename: str):
        """Load results from JSON."""
        filepath = self.output_dir / filename
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        self.results = [
            ExperimentResult(
                experiment_type=ExperimentType(r["experiment_type"]),
                run_id=r["run_id"],
                seed=r["seed"],
                baseline_metrics=r["baseline_metrics"],
                improved_metrics=r["improved_metrics"],
                differences=r["differences"],
                p_values=r["p_values"],
                effect_sizes=r["effect_sizes"],
                timestamp=datetime.fromisoformat(r["timestamp"]),
                notes=r.get("notes", ""),
            )
            for r in data.get("results", [])
        ]
        logger.info(f"Loaded {len(self.results)} results from {filepath}")


def create_standard_experiments() -> List[ExperimentConfig]:
    """Create the standard set of research experiments from the roadmap."""
    return [
        ExperimentConfig(
            experiment_type=ExperimentType.LEAKAGE_TEST,
            name="Leakage-Safe Evaluation",
            description="Compare current SMOTE-before-split pipeline vs leakage-free split-before-SMOTE",
            baseline_config={"smote_before_split": True},
            improved_config={"smote_before_split": False},
            datasets=["CIC-IDS2017"],
            metrics=["accuracy", "f1_macro", "mcc", "fpr", "fnr", "pr_auc", "per_class_recall"],
        ),
        ExperimentConfig(
            experiment_type=ExperimentType.IMBALANCE,
            name="Imbalance Handling",
            description="Compare current SMOTE vs train-only balancing + class weights + rare class retention",
            baseline_config={"smote_before_split": True, "drop_rare": True},
            improved_config={"smote_train_only": True, "drop_rare": False, "class_weight": "balanced"},
            datasets=["CIC-IDS2017"],
            metrics=["f1_macro", "mcc", "per_class_recall", "pr_auc", "minority_f1"],
        ),
        ExperimentConfig(
            experiment_type=ExperimentType.GENERALIZATION,
            name="Cross-Dataset Generalization",
            description="Train on CIC-IDS2017, test on UNSW-NB15/CIC-IDS2018",
            baseline_config={"train": "CIC-IDS2017", "test": "CIC-IDS2017"},
            improved_config={"train": "CIC-IDS2017", "test": "UNSW-NB15"},
            datasets=["CIC-IDS2017", "UNSW-NB15"],
            metrics=["accuracy", "f1_macro", "mcc", "degradation_pct"],
        ),
        ExperimentConfig(
            experiment_type=ExperimentType.ZERO_DAY,
            name="Unseen Attack Detection",
            description="Leave-one-attack-family-out with OOD detection",
            baseline_config={"closed_set": True},
            improved_config={"closed_set": False, "ood_detection": True, "abstain_threshold": 0.5},
            datasets=["CIC-IDS2017"],
            metrics=["unknown_detection_rate", "known_attack_recall", "false_unknown_rate"],
        ),
        ExperimentConfig(
            experiment_type=ExperimentType.FALSE_ALARMS,
            name="False Alarm Reduction",
            description="Calibrated threshold vs fixed threshold",
            baseline_config={"threshold": 0.5, "calibrated": False},
            improved_config={"threshold": "optimized", "calibrated": True},
            datasets=["CIC-IDS2017"],
            metrics=["fpr", "fnr", "precision", "recall", "alerts_per_hour", "analyst_burden"],
        ),
        ExperimentConfig(
            experiment_type=ExperimentType.DEPLOYMENT,
            name="Real-Time Deployment Evaluation",
            description="Sustained load test with latency/throughput/resource metrics",
            baseline_config={"test": "single_inference"},
            improved_config={"test": "sustained_load", "duration": 60, "target_fps": 1000},
            datasets=["CIC-IDS2017"],
            metrics=["p50_latency", "p95_latency", "p99_latency", "throughput_fps", "cpu", "memory", "p95_alert_latency"],
        ),
        ExperimentConfig(
            experiment_type=ExperimentType.ROBUSTNESS,
            name="Model Robustness",
            description="Perturbation testing with noise, missing features, distribution shift",
            baseline_config={"robust_training": False},
            improved_config={"robust_training": True, "augmentation": ["noise", "dropout"]},
            datasets=["CIC-IDS2017"],
            metrics=["accuracy_drop", "f1_drop", "mcc_drop", "prediction_change_rate", "robustness_gate"],
        ),
        ExperimentConfig(
            experiment_type=ExperimentType.RESPONSE,
            name="Verified Response",
            description="Simulation vs risk-gated verified response with rollback",
            baseline_config={"policy": "simulation_only"},
            improved_config={"policy": "risk_gated", "verification": True, "rollback": True},
            datasets=["CIC-IDS2017"],
            metrics=["detection_to_response_latency", "containment_success", "false_block_rate", "recovery_time"],
        ),
    ]


# Example usage:
#
# runner = ExperimentRunner()
# for exp in create_standard_experiments():
#     runner.add_experiment(exp)
#
# # Define baseline and improved functions
# def baseline_leakage(seed):
#     # Run current pipeline with SMOTE before split
#     return {"accuracy": 0.98, "f1_macro": 0.97, "mcc": 0.96}
#
# def improved_leakage(seed):
#     # Run fixed pipeline with split before SMOTE
#     return {"accuracy": 0.97, "f1_macro": 0.96, "mcc": 0.95}
#
# # Run
# runner.run_experiment(
#     ExperimentType.LEAKAGE_TEST,
#     baseline_leakage,
#     improved_leakage,
# )
#
# # Generate report
# report = runner.generate_comparison_report(runner.results)
# print(report)