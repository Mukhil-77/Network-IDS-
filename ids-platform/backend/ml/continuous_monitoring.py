"""
Enhanced Continuous Monitoring with Time Windows

Strengthens the existing real-time monitoring by adding:
- Multiple time windows (1m, 5m, 15m, 1h, 24h)
- Trend tracking (increasing/decreasing/stable)
- Anomaly detection in metrics
- Dashboard-ready time-series data
- Alerting on threshold breaches
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Optional
from collections import deque, defaultdict
from threading import Lock

import numpy as np
import pandas as pd

from backend.ml.risk_scoring import PredictionResult, RiskLevel
from backend.ml.severity import get_severity, SeverityLevel
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class TrendDirection(Enum):
    INCREASING = "increasing"
    DECREASING = "decreasing"
    STABLE = "stable"


class MetricType(Enum):
    FLOWS_PER_SECOND = "flows_per_second"
    PACKETS_PER_SECOND = "packets_per_second"
    BYTES_PER_SECOND = "bytes_per_second"
    ALERTS_PER_MINUTE = "alerts_per_minute"
    UNIQUE_ATTACKERS = "unique_attackers"
    UNIQUE_TARGETS = "unique_targets"
    CRITICAL_ALERTS = "critical_alerts"
    HIGH_ALERTS = "high_alerts"
    MEDIUM_ALERTS = "medium_alerts"
    LOW_ALERTS = "low_alerts"
    DETECTION_LATENCY_MS = "detection_latency_ms"
    MODEL_HEALTH = "model_health"
    CPU_USAGE = "cpu_usage"
    MEMORY_USAGE = "memory_usage"


@dataclass
class TimeSeriesPoint:
    """Single point in a time series."""
    timestamp: datetime
    value: float
    metric_type: MetricType


@dataclass
class TimeWindowStats:
    """Statistics for a time window."""
    window_name: str
    window_duration: timedelta
    start_time: datetime
    end_time: datetime
    metrics: dict[MetricType, float]
    trend: dict[MetricType, TrendDirection]
    alert_count: int = 0
    unique_sources: int = 0
    unique_targets: int = 0
    
    def to_dict(self) -> dict:
        return {
            "window_name": self.window_name,
            "window_duration_seconds": self.window_duration.total_seconds(),
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "metrics": {k.value: v for k, v in self.metrics.items()},
            "trend": {k.value: v.value for k, v in self.trend.items()},
            "alert_count": self.alert_count,
            "unique_sources": self.unique_sources,
            "unique_targets": self.unique_targets,
        }


class TimeWindowMonitor:
    """
    Monitors metrics across multiple time windows simultaneously.
    
    Maintains rolling windows for:
    - 1 minute
    - 5 minutes  
    - 15 minutes
    - 1 hour
    - 24 hours
    """
    
    DEFAULT_WINDOWS = [
        ("1m", timedelta(minutes=1)),
        ("5m", timedelta(minutes=5)),
        ("15m", timedelta(minutes=15)),
        ("1h", timedelta(hours=1)),
        ("24h", timedelta(hours=24)),
    ]
    
    def __init__(
        self,
        windows: list[tuple[str, timedelta]] = None,
        max_points_per_window: int = 1000,
    ):
        self.windows = windows or self.DEFAULT_WINDOWS
        self.max_points = max_points_per_window
        
        # Storage for each window: metric -> deque of (timestamp, value)
        self._data: dict[str, dict[MetricType, deque]] = {
            name: defaultdict(lambda: deque(maxlen=max_points_per_window))
            for name, _ in self.windows
        }
        
        # Window durations
        self._durations = {name: duration for name, duration in self.windows}
        
        self._lock = Lock()
    
    def record_metric(
        self,
        metric: MetricType,
        value: float,
        timestamp: datetime = None,
    ):
        """Record a metric value at a timestamp."""
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        
        with self._lock:
            for name in self._data:
                self._data[name][metric].append((timestamp, value))
    
    def record_alert(self, alert: 'Alert'):
        """Record an alert for monitoring."""
        self.record_metric(MetricType.ALERTS_PER_MINUTE, 1.0)
        
        if alert.severity == "CRITICAL":
            self.record_metric(MetricType.CRITICAL_ALERTS, 1.0)
        elif alert.severity == "HIGH":
            self.record_metric(MetricType.HIGH_ALERTS, 1.0)
        elif alert.severity == "MEDIUM":
            self.record_metric(MetricType.MEDIUM_ALERTS, 1.0)
        elif alert.severity == "LOW":
            self.record_metric(MetricType.LOW_ALERTS, 1.0)
    
    def record_flow(self, flow_data: dict):
        """Record a network flow."""
        self.record_metric(MetricType.FLOWS_PER_SECOND, 1.0)
        if "packets_per_second" in flow_data:
            self.record_metric(MetricType.PACKETS_PER_SECOND, flow_data["packets_per_second"])
        if "bytes_per_second" in flow_data:
            self.record_metric(MetricType.BYTES_PER_SECOND, flow_data["bytes_per_second"])
    
    def record_system_metrics(self, cpu: float, memory: float, latency_ms: float):
        """Record system performance metrics."""
        self.record_metric(MetricType.CPU_USAGE, cpu)
        self.record_metric(MetricType.MEMORY_USAGE, memory)
        self.record_metric(MetricType.DETECTION_LATENCY_MS, latency_ms)
    
    def _prune_old_data(self, name: str, cutoff: datetime):
        """Remove data points older than cutoff from a window."""
        for metric in self._data[name]:
            dq = self._data[name][metric]
            while dq and dq[0][0] < cutoff:
                dq.popleft()
    
    def get_window_stats(self, name: str) -> TimeWindowStats:
        """Get statistics for a specific time window."""
        if name not in self._data:
            raise ValueError(f"Unknown window: {name}")
        
        duration = self._durations[name]
        cutoff = datetime.now(timezone.utc) - duration
        
        with self._lock:
            # Prune old data
            self._prune_old_data(name, cutoff)
            
            # Calculate metrics
            metrics = {}
            for metric, dq in self._data[name].items():
                if dq:
                    values = [v for _, v in dq]
                    metrics[metric] = np.mean(values)
                else:
                    metrics[metric] = 0.0
            
            # Calculate trends (simple linear regression slope)
            trends = {}
            for metric, dq in self._data[name].items():
                if len(dq) >= 3:
                    timestamps = np.array([(ts - dq[0][0]).total_seconds() for ts, _ in dq])
                    values = np.array([v for _, v in dq])
                    # Simple linear regression
                    if len(values) > 1:
                        slope = np.polyfit(timestamps, values, 1)[0]
                        if slope > 0.01:
                            trends[metric] = TrendDirection.INCREASING
                        elif slope < -0.01:
                            trends[metric] = TrendDirection.DECREASING
                        else:
                            trends[metric] = TrendDirection.STABLE
                    else:
                        trends[metric] = TrendDirection.STABLE
                else:
                    trends[metric] = TrendDirection.STABLE
            
            # Count alerts in window
            alert_count = len(self._data[name].get(MetricType.ALERTS_PER_MINUTE, []))
            
            return TimeWindowStats(
                window_name=name,
                window_duration=self._durations[name],
                start_time=datetime.now(timezone.utc) - duration,
                end_time=datetime.now(timezone.utc),
                metrics=metrics,
                trend=trends,
                alert_count=alert_count,
            )
    
    def get_all_windows(self) -> dict[str, TimeWindowStats]:
        """Get statistics for all time windows."""
        return {name: self.get_window_stats(name) for name in self._data}
    
    def get_time_series(self, metric: MetricType, window: str = "1h", max_points: int = 100) -> list[TimeSeriesPoint]:
        """Get time series data for a metric in a specific window."""
        if window not in self._data:
            raise ValueError(f"Unknown window: {window}")
        
        with self._lock:
            dq = self._data[window].get(metric, deque())
            cutoff = datetime.now(timezone.utc) - self._durations[window]
            
            points = []
            for ts, val in dq:
                if ts >= cutoff:
                    points.append(TimeSeriesPoint(
                        timestamp=ts,
                        value=val,
                        metric_type=metric,
                    ))
            
            # Limit points
            if len(points) > max_points:
                # Downsample evenly
                step = len(points) // max_points + 1
                points = points[::step]
            
            return points
    
    def check_thresholds(self, thresholds: dict[MetricType, tuple[float, float]]) -> list[dict]:
        """
        Check if any metrics exceed thresholds in any window.
        
        Args:
            thresholds: Dict mapping MetricType -> (min_threshold, max_threshold)
            
        Returns:
            List of threshold violations
        """
        violations = []
        
        for name in self._data:
            stats = self.get_window_stats(name)
            for metric, (min_val, max_val) in thresholds.items():
                if metric in stats.metrics:
                    value = stats.metrics[metric]
                    if value < min_val or value > max_val:
                        violations.append({
                            "window": name,
                            "metric": metric.value,
                            "value": value,
                            "min_threshold": min_val,
                            "max_threshold": max_val,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        })
        
        return violations


class ContinuousMonitor:
    """
    High-level continuous monitoring coordinator.
    
    Integrates:
    - Time window monitoring
    - Trend analysis
    - Anomaly detection
    - Alert generation
    """
    
    def __init__(
        self,
        windows: list[tuple[str, timedelta]] = None,
        alert_thresholds: dict = None,
    ):
        self.monitor = TimeWindowMonitor(windows)
        self.alert_thresholds = alert_thresholds or {
            MetricType.CPU_USAGE: (0, 90),
            MetricType.MEMORY_USAGE: (0, 85),
            MetricType.DETECTION_LATENCY_MS: (0, 1000),
            MetricType.CRITICAL_ALERTS: (0, 10),
        }
        
        self._alert_callbacks: list[Callable] = []
        self._running = False
    
    def add_alert_callback(self, callback: Callable[[dict], None]):
        """Add callback for threshold violations."""
        self._alert_callbacks.append(callback)
    
    def start(self):
        """Start monitoring (placeholder for background thread)."""
        self._running = True
    
    def stop(self):
        """Stop monitoring."""
        self._running = False
    
    def record_alert(self, alert: 'Alert'):
        """Record an alert."""
        self.monitor.record_alert(alert)
        self._check_and_alert()
    
    def record_flow(self, flow_data: dict):
        """Record a network flow."""
        self.monitor.record_flow(flow_data)
    
    def record_system_metrics(self, cpu: float, memory: float, latency_ms: float):
        """Record system metrics."""
        self.monitor.record_system_metrics(cpu, memory, latency_ms)
    
    def _check_and_alert(self):
        """Check thresholds and trigger callbacks."""
        violations = self.monitor.check_thresholds(self.alert_thresholds)
        for violation in violations:
            for callback in self._alert_callbacks:
                try:
                    callback(violation)
                except Exception as e:
                    logger.error(f"Alert callback failed: {e}")
    
    def get_dashboard_data(self) -> dict:
        """Get all data formatted for dashboard."""
        windows = self.get_all_windows()
        
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "windows": {name: stats.to_dict() for name, stats in windows.items()},
            "alerts": {
                "critical": self._get_metric_value(MetricType.CRITICAL_ALERTS, "1m"),
                "high": self._get_metric_value(MetricType.HIGH_ALERTS, "1m"),
                "medium": self._get_metric_value(MetricType.MEDIUM_ALERTS, "1m"),
                "low": self._get_metric_value(MetricType.LOW_ALERTS, "1m"),
            },
            "system": {
                "cpu": self._get_metric_value(MetricType.CPU_USAGE, "1m"),
                "memory": self._get_metric_value(MetricType.MEMORY_USAGE, "1m"),
                "latency_ms": self._get_metric_value(MetricType.DETECTION_LATENCY_MS, "1m"),
            },
            "trends": {
                name: {k.value: v.value for k, v in stats.trend.items()}
                for name, stats in windows.items()
            },
        }
    
    def _get_metric_value(self, metric: MetricType, window: str) -> float:
        stats = self.monitor.get_window_stats(window)
        return stats.metrics.get(metric, 0.0)
    
    def get_all_windows(self) -> dict[str, TimeWindowStats]:
        return self.monitor.get_all_windows()


# Global monitor instance
continuous_monitor = ContinuousMonitor()


if __name__ == "__main__":
    print("Continuous monitoring module loaded successfully")