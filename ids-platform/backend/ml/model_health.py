"""
Concept Drift / Model Health Monitoring

Lightweight monitoring for changing traffic behavior and model performance degradation.
Detects possible drift and alerts the SOC without automatically retraining.

Monitors:
- Feature distribution changes (KS test, PSI)
- Prediction distribution shifts
- Performance metric degradation
- Traffic pattern changes

Status levels:
- NORMAL: Model performing within expected bounds
- WATCH: Minor drift detected, increased monitoring
- DRIFT_DETECTED: Significant drift, action recommended
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Optional, Callable
from collections import deque, defaultdict
from threading import Lock

import numpy as np
import pandas as pd
from scipy import stats

from backend.utils.logger import get_logger

logger = get_logger(__name__)


class ModelHealthStatus(Enum):
    NORMAL = "NORMAL"
    WATCH = "WATCH"
    DRIFT_DETECTED = "DRIFT_DETECTED"


@dataclass
class DriftDetectionResult:
    """Result of a drift detection check."""
    timestamp: datetime
    status: ModelHealthStatus
    drift_score: float  # 0-1, higher = more drift
    affected_features: list[str]
    drift_magnitude: dict[str, float]  # feature -> drift magnitude
    p_values: dict[str, float]  # feature -> p-value from statistical test
    recommended_action: str
    affected_samples: int = 0
    
    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "status": self.status.value,
            "drift_score": self.drift_score,
            "affected_features": self.affected_features,
            "drift_magnitude": self.drift_magnitude,
            "p_values": self.p_values,
            "recommended_action": self.recommended_action,
            "affected_samples": self.affected_samples,
        }


@dataclass
class ModelHealthSnapshot:
    """Snapshot of model health at a point in time."""
    timestamp: datetime
    status: ModelHealthStatus
    drift_score: float
    prediction_distribution: dict[str, int]  # class -> count
    feature_stats: dict[str, dict[str, float]]  # feature -> {mean, std, min, max}
    performance_metrics: dict[str, float]  # accuracy, f1, etc. if available
    drift_history: list[DriftDetectionResult] = field(default_factory=list)


class DriftDetector:
    """
    Detects concept drift using statistical tests.
    
    Methods:
    - Population Stability Index (PSI) for feature distributions
    - Kolmogorov-Smirnov test for continuous features
    - Chi-square test for categorical features
    - Prediction distribution shift detection
    """
    
    def __init__(
        self,
        reference_data: pd.DataFrame,
        feature_names: list[str],
        psi_threshold: float = 0.2,
        ks_threshold: float = 0.05,
        min_samples: int = 100,
    ):
        """
        Initialize drift detector with reference data.
        
        Args:
            reference_data: Baseline training/validation data (PCA features)
            feature_names: List of feature names to monitor
            psi_threshold: PSI threshold for drift detection (0.1=small, 0.2=moderate, >0.2=large)
            ks_threshold: p-value threshold for KS test
            min_samples: Minimum samples needed for drift detection
        """
        self.reference_data = reference_data
        self.feature_names = feature_names
        self.psi_threshold = psi_threshold
        self.ks_threshold = ks_threshold
        self.min_samples = min_samples
        
        # Compute reference statistics
        self._reference_stats = self._compute_reference_stats(reference_data)
        
        # History
        self.drift_history: list = []
        self._lock = Lock()
    
    def _compute_reference_stats(self, df: pd.DataFrame) -> dict[str, dict]:
        """Compute reference statistics for each feature."""
        stats = {}
        for feat in self.feature_names:
            if feat in df.columns:
                vals = df[feat].dropna().values
                stats[feat] = {
                    "mean": float(np.mean(vals)),
                    "std": float(np.std(vals)),
                    "min": float(np.min(vals)),
                    "max": float(np.max(vals)),
                    "quantiles": np.percentile(vals, [0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99]).tolist(),
                    "histogram": np.histogram(vals, bins=10, density=True)[0].tolist(),
                    "hist_bins": np.histogram(vals, bins=10, density=True)[1].tolist(),
                }
        return stats
    
    def compute_psi(self, reference: np.ndarray, current: np.ndarray, bins: int = 10) -> float:
        """
        Compute Population Stability Index (PSI) between two distributions.
        
        PSI = sum((actual_i - expected_i) * ln(actual_i / expected_i))
        """
        # Create bins based on reference data
        _, bins = np.histogram(reference, bins=10)
        
        # Ensure bins cover the full range
        bins[0] = -np.inf
        bins[-1] = np.inf
        
        ref_hist, _ = np.histogram(reference, bins=bins, density=True)
        cur_hist, _ = np.histogram(current, bins=bins, density=True)
        
        # Avoid division by zero
        ref_hist = np.maximum(ref_hist, 1e-10)
        cur_hist = np.maximum(cur_hist, 1e-10)
        
        psi = np.sum((cur_hist - ref_hist) * np.log(cur_hist / ref_hist))
        return float(psi)
    
    def compute_ks_test(self, reference: np.ndarray, current: np.ndarray) -> tuple[float, float]:
        """
        Perform Kolmogorov-Smirnov test between two distributions.
        
        Returns:
            (ks_statistic, p_value)
        """
        ks_stat, p_value = stats.ks_2samp(reference, current)
        return float(ks_stat), float(p_value)
    
    def check_drift(self, current_data: pd.DataFrame) -> DriftDetectionResult:
        """
        Check for drift in current data compared to reference.
        
        Args:
            current_data: New data to check for drift (same features as reference)
            
        Returns:
            DriftDetectionResult with drift assessment
        """
        if len(current_data) < self.min_samples:
            return DriftDetectionResult(
                timestamp=datetime.now(timezone.utc),
                status=ModelHealthStatus.NORMAL,
                drift_score=0.0,
                affected_features=[],
                drift_magnitude={},
                p_values={},
                recommended_action="Insufficient samples for drift detection",
                affected_samples=len(current_data),
            )
        
        affected_features = []
        drift_magnitudes = {}
        p_values = {}
        drift_scores = []
        
        for feat in self.feature_names:
            if feat not in current_data.columns or feat not in self._reference_stats:
                continue
            
            ref_vals = self.reference_data[feat].dropna().values
            cur_vals = current_data[feat].dropna().values
            
            if len(cur_vals) < 10:
                continue
            
            # PSI test
            psi = self.compute_psi(ref_vals, current_data[feat].values)
            drift_magnitudes[f"{feat}_psi"] = psi
            
            # KS test
            ks_stat, p_value = self.compute_ks_test(
                self.reference_data[feat].values,
                current_data[feat].values
            )
            p_values[feat] = p_value
            
            # Check if drift detected
            drift_detected = False
            if psi > self.psi_threshold:
                affected_features.append(feat)
                drift_detected = True
            if p_value < self.ks_threshold:
                if feat not in affected_features:
                    affected_features.append(feat)
                drift_detected = True
            
            drift_scores.append(psi)
        
        # Overall drift score (max PSI)
        overall_drift_score = max(drift_scores) if drift_scores else 0.0
        
        # Determine status
        if overall_drift_score > self.psi_threshold * 2:
            status = ModelHealthStatus.DRIFT_DETECTED
            action = "Significant drift detected. Review model performance and consider retraining."
        elif overall_drift_score > self.psi_threshold:
            status = ModelHealthStatus.WATCH
            action = "Moderate drift detected. Increase monitoring frequency and review feature distributions."
        else:
            status = ModelHealthStatus.NORMAL
            action = "Model healthy. No significant drift detected."
        
        return DriftDetectionResult(
            timestamp=datetime.now(timezone.utc),
            status=status,
            drift_score=float(overall_drift_score),
            affected_features=affected_features,
            drift_magnitude=drift_magnitudes,
            p_values=p_values,
            recommended_action=action,
            affected_samples=len(current_data),
        )
    
    def check_prediction_drift(
        self,
        predictions: np.ndarray,
        reference_predictions: np.ndarray = None,
    ) -> DriftDetectionResult:
        """
        Check for drift in prediction distribution.
        
        Args:
            predictions: Current predictions (class labels or probabilities)
            reference_predictions: Reference predictions (from training period)
        """
        if reference_predictions is None:
            return DriftDetectionResult(
                timestamp=datetime.now(timezone.utc),
                status=ModelHealthStatus.NORMAL,
                drift_score=0.0,
                affected_features=[],
                drift_magnitude={},
                p_values={},
                recommended_action="No reference predictions available",
                affected_samples=0,
            )
        
        # Chi-square test for prediction distribution shift
        pred_unique, pred_counts = np.unique(predictions, return_counts=True)
        ref_unique, ref_counts = np.unique(reference_predictions, return_counts=True)
        
        # Align classes
        all_classes = np.union1d(pred_unique, ref_unique)
        pred_aligned = np.array([np.sum(predictions == c) for c in all_classes])
        ref_aligned = np.array([np.sum(reference_predictions == c) for c in all_classes])
        
        # Chi-square test
        chi2, p_value = stats.chisquare(pred_aligned, ref_aligned)
        
        drift_detected = p_value < 0.05
        
        return DriftDetectionResult(
            timestamp=datetime.now(timezone.utc),
            status=ModelHealthStatus.DRIFT_DETECTED if drift_detected else ModelHealthStatus.NORMAL,
            drift_score=float(chi2),
            affected_features=["prediction_distribution"] if drift_detected else [],
            drift_magnitude={"chi2": float(chi2)},
            p_values={"prediction_shift": float(p_value)},
            recommended_action="Prediction distribution shifted. Investigate data changes." if drift_detected else "Prediction distribution stable.",
            affected_samples=len(predictions),
        )


class ModelHealthMonitor:
    """
    High-level model health monitoring coordinator.
    
    Integrates:
    - Feature drift detection (PSI, KS test)
    - Prediction distribution monitoring
    - Performance tracking (when labels available)
    - Automated health status updates
    """
    
    def __init__(
        self,
        reference_data: pd.DataFrame,
        feature_names: list[str],
        drift_threshold: float = 0.2,
        check_interval_minutes: int = 60,
    ):
        self.drift_detector = DriftDetector(
            reference_data=reference_data,
            feature_names=feature_names,
            psi_threshold=drift_threshold,
        )
        self.check_interval = timedelta(minutes=check_interval_minutes)
        self.last_check: Optional[datetime] = None
        
        self.current_status = ModelHealthStatus.NORMAL
        self.drift_history: list[DriftDetectionResult] = []
        self.performance_history: list[dict] = []
        
        self._lock = Lock()
    
    def update_reference(self, new_reference: pd.DataFrame):
        """Update reference data (e.g., after retraining)."""
        self.drift_detector = DriftDetector(
            reference_data=new_reference,
            feature_names=self.drift_detector.feature_names,
            psi_threshold=self.drift_detector.psi_threshold,
        )
        logger.info("Updated drift detector reference data")
    
    def check_health(self, current_data: pd.DataFrame) -> DriftDetectionResult:
        """Run drift detection on current data."""
        with self._lock:
            result = self.drift_detector.check_drift(current_data)
            self.current_status = result.status
            self.drift_history.append(result)
            self.last_check = datetime.now(timezone.utc)
            
            # Keep history bounded
            if len(self.drift_history) > 1000:
                self.drift_history = self.drift_history[-1000:]
            
            return result
    
    def check_prediction_drift(
        self,
        predictions: np.ndarray,
        reference_predictions: np.ndarray = None,
    ) -> DriftDetectionResult:
        """Check for prediction distribution drift."""
        result = self.drift_detector.check_prediction_drift(
            predictions, reference_predictions
        )
        self.drift_history.append(result)
        return result
    
    def record_performance(self, metrics: dict[str, float]):
        """Record model performance metrics."""
        self.performance_history.append({
            "timestamp": datetime.now(timezone.utc),
            **metrics,
        })
        if len(self.performance_history) > 1000:
            self.performance_history = self.performance_history[-1000:]
    
    def get_health_summary(self) -> dict:
        """Get current model health summary."""
        recent_drifts = self.drift_history[-10:] if self.drift_history else []
        
        return {
            "current_status": self.current_status.value,
            "last_check": self.last_check.isoformat() if self.last_check else None,
            "total_drift_checks": len(self.drift_history),
            "drift_detected_count": sum(1 for d in self.drift_history if d.status == ModelHealthStatus.DRIFT_DETECTED),
            "watch_count": sum(1 for d in self.drift_history if d.status == ModelHealthStatus.WATCH),
            "recent_drift_scores": [d.drift_score for d in recent_drifts],
            "avg_drift_score": np.mean([d.drift_score for d in recent_drifts]) if recent_drifts else 0.0,
            "performance_history_length": len(self.performance_history),
            "latest_performance": self.performance_history[-1] if self.performance_history else None,
        }
    
    def get_drift_report(self) -> str:
        """Generate human-readable drift report."""
        lines = []
        lines.append("=" * 80)
        lines.append("MODEL HEALTH / DRIFT REPORT")
        lines.append("=" * 80)
        
        summary = self.get_health_summary()
        lines.append(f"\nCurrent Status: {summary['current_status']}")
        lines.append(f"Last Check: {summary['last_check'] or 'Never'}")
        lines.append(f"Total Checks: {summary['total_drift_checks']}")
        lines.append(f"Drift Detected: {summary['drift_detected_count']}")
        lines.append(f"Watch State: {summary['watch_count']}")
        
        if self.drift_history:
            lines.append("\nRecent Drift Checks:")
            for d in self.drift_history[-5:]:
                lines.append(
                    f"  {d.timestamp.strftime('%Y-%m-%d %H:%M:%S')} | "
                    f"{d.status.value} | Score: {d.drift_score:.4f} | "
                    f"Affected: {', '.join(d.affected_features) or 'None'} | "
                    f"Action: {d.recommended_action}"
                )
        
        if self.performance_history:
            lines.append("\nLatest Performance:")
            perf = self.performance_history[-1]
            for k, v in perf.items():
                if k != "timestamp":
                    lines.append(f"  {k}: {v}")
        
        return "\n".join(lines)


class ModelHealthManager:
    """
    High-level model health management.
    
    Coordinates:
    - Periodic drift checks
    - Performance tracking
    - Alerting on drift
    - Integration with SOC dashboard
    """
    
    def __init__(
        self,
        reference_data: pd.DataFrame,
        feature_names: list[str],
        check_interval_minutes: int = 60,
    ):
        self.health_monitor = ModelHealthMonitor(
            reference_data=reference_data,
            feature_names=feature_names,
            drift_threshold=0.2,
            check_interval_minutes=60,
        )
        self.check_interval = timedelta(minutes=check_interval_minutes)
        self._last_check_time: Optional[datetime] = None
        self._alert_callbacks: list[Callable] = []
    
    def add_alert_callback(self, callback: Callable[[DriftDetectionResult], None]):
        """Add callback for drift alerts."""
        pass
    
    def check_and_report(self, current_data: pd.DataFrame) -> Optional[DriftDetectionResult]:
        """Run health check if interval has passed."""
        now = datetime.now(timezone.utc)
        
        if self._last_check_time is None or (now - self._last_check_time) >= self.health_monitor.check_interval:
            self._last_check_time = now
            return self.health_monitor.check_health(current_data)
        
        return None
    
    def get_health_dashboard_data(self) -> dict:
        """Get data formatted for dashboard."""
        summary = self.health_monitor.get_health_summary()
        
        return {
            "status": summary["current_status"],
            "last_check": summary["last_check"],
            "drift_score": summary["avg_drift_score"],
            "drift_detected_count": summary["drift_detected_count"],
            "watch_count": summary["watch_count"],
            "total_checks": summary["total_drift_checks"],
            "drift_history": [d.to_dict() for d in self.health_monitor.drift_history[-20:]],
            "performance": summary["latest_performance"],
        }


if __name__ == "__main__":
    print("Concept drift / model health monitoring module loaded successfully")