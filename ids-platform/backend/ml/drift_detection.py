"""
Concept drift detection and model health monitoring.

Monitors feature distributions and model performance for drift detection.
Provides early warning for model degradation.

Research contribution: Deployment-aware continuous IDS evaluation with model health monitoring.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from collections import deque, defaultdict
import numpy as np
import pandas as pd
from scipy import stats
import warnings

from backend.utils.logger import get_logger

logger = get_logger(__name__)


class DriftSeverity(Enum):
    """Drift severity levels."""
    NORMAL = "NORMAL"
    WATCH = "WATCH"
    DRIFT_DETECTED = "DRIFT_DETECTED"
    SEVERE_DRIFT = "SEVERE_DRIFT"


@dataclass
class DriftReport:
    """Report for a single feature drift check."""
    feature_name: str
    drift_detected: bool
    severity: DriftSeverity
    psi: float  # Population Stability Index
    ks_statistic: float
    ks_pvalue: float
    reference_mean: float
    current_mean: float
    reference_std: float
    current_std: float
    timestamp: datetime
    recommended_action: str


@dataclass
class ModelHealthReport:
    """Overall model health assessment."""
    status: DriftSeverity
    timestamp: datetime
    feature_drifts: List[DriftReport]
    performance_degradation: Optional[float] = None
    confidence_degradation: Optional[float] = None
    recommendations: List[str] = field(default_factory=list)
    affected_features: List[str] = field(default_factory=list)


class DriftDetector:
    """
    Concept drift detector using Population Stability Index (PSI)
    and Kolmogorov-Smirnov test.
    
    Monitors feature distributions for drift detection.
    """
    
    def __init__(
        self,
        reference_data: Optional[np.ndarray] = None,
        feature_names: Optional[List[str]] = None,
        psi_threshold_watch: float = 0.1,
        psi_threshold_drift: float = 0.2,
        psi_threshold_severe: float = 0.5,
        ks_alpha: float = 0.05,
        window_size: int = 1000,
        min_samples: int = 100,
    ):
        """
        Initialize drift detector.
        
        Args:
            reference_data: Reference distribution (n_samples, n_features)
            feature_names: Names of features
            psi_threshold_watch: PSI threshold for WATCH level
            psi_threshold_drift: PSI threshold for DRIFT level
            psi_threshold_severe: PSI threshold for SEVERE level
            ks_alpha: Significance level for KS test
            window_size: Number of recent samples to maintain for current distribution
            min_samples: Minimum samples needed before drift detection runs
        """
        self.feature_names = feature_names or []
        self.psi_thresholds = {
            "watch": psi_threshold_watch,
            "drift": psi_threshold_drift,
            "severe": psi_threshold_severe,
        }
        self.ks_alpha = ks_alpha
        self.window_size = window_size
        self.min_samples = min_samples
        
        # Reference distribution (training data statistics)
        self.reference_stats: Dict[str, Dict[str, float]] = {}
        self.reference_histograms: Dict[str, np.ndarray] = {}
        self.reference_bins: Dict[str, np.ndarray] = {}
        
        # Current window buffer
        self.current_buffer: List[np.ndarray] = []
        self.buffer_lock = False
        
        # Drift history
        self.drift_history: List[ModelHealthReport] = []
        
        if reference_data is not None:
            self.set_reference(reference_data)
    
    def set_reference(self, reference_data: np.ndarray, feature_names: Optional[List[str]] = None):
        """Set reference distribution from training data."""
        if feature_names:
            self.feature_names = feature_names
        
        n_features = reference_data.shape[1]
        if len(self.feature_names) != n_features:
            self.feature_names = [f"feature_{i}" for i in range(n_features)]
        
        logger.info(f"Setting reference distribution: {reference_data.shape[0]} samples, {n_features} features")
        
        for i, name in enumerate(self.feature_names):
            col_data = reference_data[:, i]
            # Remove NaN/inf
            clean_data = col_data[np.isfinite(col_data)]
            
            if len(clean_data) == 0:
                logger.warning(f"Feature {name} has no valid data in reference")
                continue
            
            # Compute statistics
            self.reference_stats[name] = {
                "mean": float(np.mean(clean_data)),
                "std": float(np.std(clean_data)),
                "min": float(np.min(clean_data)),
                "max": float(np.max(clean_data)),
                "median": float(np.median(clean_data)),
                "q25": float(np.percentile(clean_data, 25)),
                "q75": float(np.percentile(clean_data, 75)),
                "count": len(clean_data),
            }
            
            # Create histogram for PSI calculation
            hist, bins = np.histogram(clean_data, bins=10, density=True)
            self.reference_histograms[name] = hist
            self.reference_bins[name] = bins
        
        logger.info(f"Reference set for {len(self.reference_stats)} features")
    
    def add_sample(self, sample: np.ndarray):
        """Add a sample to the current buffer."""
        if self.buffer_lock:
            return
        
        self.current_buffer.append(sample)
        if len(self.current_buffer) > self.window_size:
            self.current_buffer.pop(0)
    
    def add_batch(self, batch: np.ndarray):
        """Add a batch of samples."""
        for sample in batch:
            self.add_sample(sample)
    
    def _compute_psi(self, reference_hist: np.ndarray, current_hist: np.ndarray) -> float:
        """Compute Population Stability Index (PSI)."""
        # Avoid division by zero
        eps = 1e-10
        ref = np.maximum(reference_hist, eps)
        cur = np.maximum(current_hist, eps)
        psi = np.sum((cur - ref) * np.log(cur / ref))
        return float(psi)
    
    def _compute_ks_test(self, ref_data: np.ndarray, cur_data: np.ndarray) -> Tuple[float, float]:
        """Compute Kolmogorov-Smirnov test statistic and p-value."""
        # Use scipy's KS test
        try:
            stat, pval = stats.ks_2samp(ref_data, cur_data)
            return float(stat), float(pval)
        except Exception as e:
            logger.warning(f"KS test failed: {e}")
            return 0.0, 1.0
    
    def check_drift(self, current_data: Optional[np.ndarray] = None) -> ModelHealthReport:
        """
        Check for drift in current distribution vs reference.
        
        Args:
            current_data: Optional current data. If None, uses internal buffer.
            
        Returns:
            ModelHealthReport with drift assessment
        """
        if current_data is None:
            if len(self.current_buffer) < self.min_samples:
                return ModelHealthReport(
                    status=DriftSeverity.NORMAL,
                    timestamp=datetime.now(),
                    feature_drifts=[],
                    recommendations=["Insufficient samples for drift detection"],
                )
            current_data = np.array(self.current_buffer)
        
        if not self.reference_stats:
            return ModelHealthReport(
                status=DriftSeverity.NORMAL,
                timestamp=datetime.now(),
                feature_drifts=[],
                recommendations=["No reference distribution set"],
            )
        
        feature_reports = []
        drift_detected_any = False
        severe_drift_any = False
        affected_features = []
        
        for name in self.feature_names:
            if name not in self.reference_stats:
                continue
            
            ref_stats = self.reference_stats[name]
            
            # Get current data for this feature
            if name in self.feature_names:
                idx = self.feature_names.index(name)
                if current_data.ndim == 2 and current_data.shape[1] > idx:
                    cur_data = current_data[:, idx]
                else:
                    continue
            else:
                continue
            
            # Clean current data
            cur_clean = current_data[np.isfinite(current_data)]
            if len(cur_clean) < 10:
                continue
            
            # Get reference data for KS test (we need raw data, not just stats)
            # For PSI, we use histograms
            ref_hist = self.reference_histograms.get(name)
            ref_bins = self.reference_bins.get(name)
            
            if ref_hist is None or ref_bins is None:
                continue
            
            # Compute current histogram with same bins
            cur_hist, _ = np.histogram(cur_data, bins=ref_bins, density=True)
            
            # Compute PSI
            psi = self._compute_psi(ref_hist, cur_hist)
            
            # KS test on raw data
            # We need reference raw data - approximate from stats
            # For now, use normal approximation
            ref_mean = self.reference_stats[name]["mean"]
            ref_std = self.reference_stats[name]["std"]
            # Generate synthetic reference data for KS test
            ref_synthetic = np.random.normal(ref_mean, ref_std, 10000)
            ks_stat, ks_pvalue = self._compute_ks_test(ref_synthetic, cur_data)
            
            # Determine severity
            if psi >= self.psi_thresholds["severe"]:
                severity = DriftSeverity.SEVERE_DRIFT
                severe_drift_any = True
            elif psi >= self.psi_thresholds["drift"]:
                severity = DriftSeverity.DRIFT_DETECTED
                drift_detected_any = True
            elif psi >= self.psi_thresholds["watch"]:
                severity = DriftSeverity.WATCH
            else:
                severity = DriftSeverity.NORMAL
            
            # Determine action
            if severity == DriftSeverity.SEVERE_DRIFT:
                action = "CRITICAL: Severe drift detected. Immediate model review required. Consider retraining."
            elif severity == DriftSeverity.DRIFT_DETECTED:
                action = "WARNING: Drift detected. Monitor closely. Schedule model review."
            elif severity == DriftSeverity.WATCH:
                action = "INFO: Early drift signals. Increase monitoring frequency."
            else:
                action = "OK: No significant drift detected."
            
            report = DriftReport(
                feature_name=name,
                drift_detected=severity != DriftSeverity.NORMAL,
                severity=severity,
                psi=psi,
                ks_statistic=ks_stat,
                ks_pvalue=ks_pvalue,
                reference_mean=self.reference_stats[name]["mean"],
                current_mean=float(np.mean(cur_data)),
                reference_std=self.reference_stats[name]["std"],
                current_std=float(np.std(cur_data)),
                timestamp=datetime.now(),
                recommended_action=action,
            )
            
            feature_reports.append(report)
            
            if severity in (DriftSeverity.DRIFT_DETECTED, DriftSeverity.SEVERE_DRIFT):
                affected_features.append(name)
                drift_detected_any = True
        
        # Determine overall status
        if severe_drift_any:
            overall_status = DriftSeverity.SEVERE_DRIFT
        elif drift_detected_any:
            overall_status = DriftSeverity.DRIFT_DETECTED
        elif any(r.severity == DriftSeverity.WATCH for r in feature_reports):
            overall_status = DriftSeverity.WATCH
        else:
            overall_status = DriftSeverity.NORMAL
        
        # Generate recommendations
        recommendations = []
        if overall_status == DriftSeverity.SEVERE_DRIFT:
            recommendations.extend([
                "Severe drift detected in multiple features.",
                "Immediate model review and retraining recommended.",
                "Consider emergency model rollback to previous version.",
                "Investigate root cause of distribution shift.",
            ])
        elif overall_status == DriftSeverity.DRIFT_DETECTED:
            recommendations.extend([
                "Drift detected in one or more features.",
                "Schedule model retraining within 24-48 hours.",
                "Increase monitoring frequency.",
                "Review affected features: " + ", ".join(affected_features),
            ])
        elif overall_status == DriftSeverity.WATCH:
            recommendations.extend([
                "Early drift signals detected.",
                "Increase monitoring frequency to hourly.",
                "Prepare retraining pipeline.",
            ])
        else:
            recommendations.append("Model health normal. Continue routine monitoring.")
        
        report = ModelHealthReport(
            status=overall_status,
            timestamp=datetime.now(),
            feature_drifts=feature_reports,
            affected_features=affected_features,
            recommendations=recommendations,
        )
        
        # Store in history
        self.drift_history.append(report)
        if len(self.drift_history) > 1000:
            self.drift_history.pop(0)
        
        return report
    
    def get_drift_summary(self) -> Dict[str, Any]:
        """Get summary of current drift status."""
        if not self.drift_history:
            return {"status": "no_data", "message": "No drift checks performed yet"}
        
        latest = self.drift_history[-1]
        return {
            "status": latest.status.value,
            "timestamp": latest.timestamp.isoformat(),
            "drifted_features": len([f for f in latest.feature_drifts if f.drift_detected]),
            "total_features_monitored": len(latest.feature_drifts),
            "affected_features": latest.affected_features,
            "recommendations": latest.recommendations,
        }
    
    def get_feature_drift_detail(self, feature_name: str) -> Optional[Dict[str, Any]]:
        """Get detailed drift info for a specific feature."""
        if not self.drift_history:
            return None
        
        latest = self.drift_history[-1]
        for report in latest.feature_drifts:
            if report.feature_name == feature_name:
                return {
                    "feature": feature_name,
                    "drift_detected": report.drift_detected,
                    "severity": report.severity.value,
                    "psi": report.psi,
                    "ks_statistic": report.ks_statistic,
                    "ks_pvalue": report.ks_pvalue,
                    "reference_mean": report.reference_mean,
                    "current_mean": report.current_mean,
                    "reference_std": report.reference_std,
                    "current_std": report.current_std,
                    "timestamp": report.timestamp.isoformat(),
                    "recommended_action": report.recommended_action,
                }
        return None


class PerformanceMonitor:
    """
    Monitors model performance metrics for degradation detection.
    """
    
    def __init__(self, window_size: int = 1000):
        self.window_size = window_size
        self.predictions: deque = deque(maxlen=window_size)
        self.ground_truth: deque = deque(maxlen=window_size)
        self.latencies: deque = deque(maxlen=window_size)
        self.confidences: deque = deque(maxlen=window_size)
    
    def record_prediction(
        self, 
        y_true: int, 
        y_pred: int, 
        confidence: float, 
        latency_ms: float
    ):
        """Record a prediction for performance monitoring."""
        self.predictions.append(y_pred)
        self.ground_truth.append(y_true)
        self.confidences.append(confidence)
        self.latencies.append(latency_ms)
    
    def get_performance_metrics(self) -> Dict[str, float]:
        """Compute current performance metrics."""
        if len(self.predictions) < 10:
            return {}
        
        y_true = np.array(self.ground_truth)
        y_pred = np.array(self.predictions)
        confidences = np.array(self.confidences)
        latencies = np.array(self.latencies)
        
        from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
        
        return {
            "accuracy": float(accuracy_score(y_true, y_pred)),
            "f1_macro": float(f1_score(y_true, y_pred, average='macro', zero_division=0)),
            "precision_macro": float(precision_score(y_true, y_pred, average='macro', zero_division=0)),
            "recall_macro": float(recall_score(y_true, y_pred, average='macro', zero_division=0)),
            "avg_confidence": float(np.mean(confidences)),
            "avg_latency_ms": float(np.mean(latencies)),
            "p95_latency_ms": float(np.percentile(latencies, 95)),
            "sample_count": len(y_true),
        }
    
    def detect_performance_degradation(
        self, 
        baseline_metrics: Dict[str, float],
        threshold: float = 0.05
    ) -> Dict[str, Any]:
        """
        Detect performance degradation vs baseline.
        
        Args:
            baseline_metrics: Baseline metrics from training/validation
            threshold: Relative degradation threshold (e.g., 0.05 = 5%)
            
        Returns:
            Degradation report
        """
        current = self.get_performance_metrics()
        if not current:
            return {"status": "insufficient_data"}
        
        degradations = {}
        alerts = []
        
        for metric, baseline_val in baseline_metrics.items():
            if metric not in current:
                continue
            current_val = current[metric]
            if baseline_val == 0:
                continue
            degradation = (baseline_val - current_val) / baseline_val
            degradations[metric] = degradation
            
            if degradation > threshold:
                alerts.append(f"{metric}: degraded by {degradation:.1%} (baseline: {baseline_val:.4f}, current: {current_val:.4f})")
        
        status = "degraded" if alerts else "normal"
        
        return {
            "status": status,
            "current_metrics": current,
            "baseline_metrics": baseline_metrics,
            "degradations": degradations,
            "alerts": alerts,
            "threshold": threshold,
        }


# Example usage:
#
# detector = DriftDetector(reference_data=X_train, feature_names=feature_names)
#
# # During live operation
# for batch in live_data_stream:
#     detector.add_batch(batch)
#     
#     if batch_count % 100 == 0:
#         report = detector.check_drift()
#         if report.status != DriftSeverity.NORMAL:
#             logger.warning(f"Drift detected: {report.status.value}")
#             for rec in report.recommendations:
#                 logger.warning(f"  - {rec}")