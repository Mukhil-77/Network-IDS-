"""
Continuous monitoring and metrics for IDS.

Provides time-windowed metrics, trend tracking, and real-time
system health monitoring for the SOC dashboard.

Research contribution: Deployment-aware continuous IDS evaluation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Deque
from collections import deque, defaultdict
from threading import Lock
import time
import statistics

from backend.utils.logger import get_logger

logger = get_logger(__name__)


class TimeWindow(Enum):
    """Predefined time windows for metrics."""
    ONE_MINUTE = timedelta(minutes=1)
    FIVE_MINUTES = timedelta(minutes=5)
    FIFTEEN_MINUTES = timedelta(minutes=15)
    ONE_HOUR = timedelta(hours=1)
    SIX_HOURS = timedelta(hours=6)
    TWENTY_FOUR_HOURS = timedelta(hours=24)


@dataclass
class MetricPoint:
    """Single metric data point with timestamp."""
    timestamp: datetime
    value: float
    labels: Dict[str, str] = field(default_factory=dict)


@dataclass
class TimeSeriesMetric:
    """Time-series metric with multiple time windows."""
    name: str
    unit: str
    points: Deque[MetricPoint] = field(default_factory=lambda: deque(maxlen=10000))
    windows: Dict[str, Deque[MetricPoint]] = field(default_factory=dict)
    
    def __post_init__(self):
        # Initialize windows
        for window in TimeWindow:
            self.windows[window.value] = deque(maxlen=1000)
    
    def add_point(self, value: float, timestamp: Optional[datetime] = None, labels: Optional[Dict] = None):
        """Add a data point and update windowed aggregates."""
        ts = timestamp or datetime.now()
        point = MetricPoint(timestamp=ts, value=value, labels=labels or {})
        self.points.append(point)
        
        # Update windows
        for window_enum in TimeWindow:
            window_delta = window_enum.value
            cutoff = ts - window_delta
            # Add to window
            self.windows[window_delta].append(point)
            # Clean old points
            while self.windows[window_delta] and self.windows[window_delta][0].timestamp < cutoff:
                self.windows[window_delta].popleft()
    
    def get_latest(self) -> Optional[float]:
        return self.points[-1].value if self.points else None
    
    def get_window_stats(self, window: TimeWindow) -> Dict[str, float]:
        """Get statistics for a time window."""
        window_delta = window.value
        points = [p.value for p in self.windows[window_delta]]
        if not points:
            return {}
        return {
            "count": len(points),
            "min": min(points),
            "max": max(points),
            "mean": statistics.mean(points),
            "median": statistics.median(points),
            "stdev": statistics.stdev(points) if len(points) > 1 else 0.0,
            "latest": points[-1],
        }
    
    def get_trend(self, window: TimeWindow, periods: int = 5) -> Dict[str, Any]:
        """Compute trend over window (increasing/decreasing/stable)."""
        points = list(self.windows[window.value])
        if len(points) < 2:
            return {"trend": "insufficient_data"}
        
        # Split into periods and compute slope
        values = [p.value for p in points]
        n = len(values)
        x = list(range(n))
        
        # Simple linear regression
        x_mean = sum(x) / n
        y_mean = sum(values) / n
        numerator = sum((x[i] - x_mean) * (values[i] - y_mean) for i in range(n))
        denominator = sum((x[i] - x_mean) ** 2 for i in range(n))
        
        if denominator == 0:
            slope = 0
        else:
            slope = numerator / denominator
        
        # Classify trend
        if abs(slope) < 0.01 * statistics.mean(values):
            trend = "stable"
        elif slope > 0:
            trend = "increasing"
        else:
            trend = "decreasing"
        
        return {
            "trend": trend,
            "slope": slope,
            "current": values[-1],
            "change_pct": (slope * n / y_mean * 100) if y_mean != 0 else 0,
        }


class MonitoringSystem:
    """
    Continuous monitoring system for IDS metrics.
    
    Tracks:
    - Total flows
    - Packets/flows per second
    - Normal vs suspicious vs attack traffic
    - Unique attackers/targets
    - High-risk/critical alerts
    - Detection latency
    - System health (CPU, memory, model status)
    """
    
    def __init__(self):
        self.metrics: Dict[str, TimeSeriesMetric] = {}
        self.lock = Lock()
        self._init_default_metrics()
    
    def _init_default_metrics(self):
        """Initialize standard IDS metrics."""
        default_metrics = [
            ("flows_total", "count", "Total flows processed"),
            ("flows_per_second", "flows/sec", "Flow throughput"),
            ("packets_per_second", "pkts/sec", "Packet throughput"),
            ("normal_traffic", "count", "Normal (BENIGN) flows"),
            ("suspicious_traffic", "count", "Suspicious/unknown flows"),
            ("attack_traffic", "count", "Confirmed attack flows"),
            ("unique_attackers", "count", "Unique source IPs with alerts"),
            ("unique_targets", "count", "Unique destination IPs with alerts"),
            ("high_risk_alerts", "count", "HIGH/CRITICAL risk alerts"),
            ("critical_alerts", "count", "CRITICAL risk alerts"),
            ("detection_latency_ms", "ms", "Flow-to-alert latency"),
            ("inference_latency_ms", "ms", "Model inference latency"),
            ("model_status", "status", "Model health (1=healthy, 0=degraded)"),
            ("feature_coverage_avg", "ratio", "Average feature coverage ratio"),
            ("cpu_usage_percent", "%", "CPU utilization"),
            ("memory_usage_mb", "MB", "Memory usage"),
        ]
        
        for name, unit, _ in default_metrics:
            self.metrics[name] = TimeSeriesMetric(name=name, unit=unit)
    
    def record(self, metric_name: str, value: float, labels: Optional[Dict] = None):
        """Record a metric value."""
        with self.lock:
            if metric_name not in self.metrics:
                self.metrics[metric_name] = TimeSeriesMetric(name=metric_name, unit="")
            self.metrics[metric_name].add_point(value, labels=labels)
    
    def record_flow(self, is_attack: bool, source_ip: str, dest_ip: str, latency_ms: float):
        """Record a processed flow."""
        self.record("flows_total", 1)
        if is_attack:
            self.record("attack_traffic", 1)
        else:
            self.record("normal_traffic", 1)
        self.record("detection_latency_ms", latency_ms)
        
        # Track unique attackers/targets (approximate with HyperLogLog would be better)
        # For now just count
        # In production, use HyperLogLog or similar
    
    def record_alert(self, risk_tier: str, source_ip: str, dest_ip: str):
        """Record an alert."""
        self.record("high_risk_alerts", 1 if risk_tier in ("HIGH", "CRITICAL") else 0)
        self.record("critical_alerts", 1 if risk_tier == "CRITICAL" else 0)
    
    def record_inference_latency(self, latency_ms: float):
        """Record model inference latency."""
        self.record("inference_latency_ms", latency_ms)
    
    def record_system_health(self, cpu_percent: float, memory_mb: float, model_healthy: bool):
        """Record system health metrics."""
        self.record("cpu_usage_percent", cpu_percent)
        self.record("memory_usage_mb", memory_mb)
        self.record("model_status", 1.0 if model_healthy else 0.0)
    
    def record_feature_coverage(self, coverage_ratio: float):
        """Record feature coverage ratio."""
        self.record("feature_coverage_avg", coverage_ratio)
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """Get all metrics formatted for dashboard."""
        with self.lock:
            data = {}
            for name, metric in self.metrics.items():
                latest = metric.get_latest()
                if latest is not None:
                    data[name] = {
                        "current": latest,
                        "unit": metric.unit,
                        "1m": metric.get_window_stats(TimeWindow.ONE_MINUTE),
                        "5m": metric.get_window_stats(TimeWindow.FIVE_MINUTES),
                        "15m": metric.get_window_stats(TimeWindow.FIFTEEN_MINUTES),
                        "1h": metric.get_window_stats(TimeWindow.ONE_HOUR),
                        "trend_1h": metric.get_trend(TimeWindow.ONE_HOUR),
                    }
            return data
    
    def get_alert_summary(self, window: TimeWindow = TimeWindow.FIFTEEN_MINUTES) -> Dict[str, Any]:
        """Get alert summary for time window."""
        with self.lock:
            return {
                "attack_traffic": self.metrics.get("attack_traffic", TimeSeriesMetric("", "")).get_window_stats(window),
                "high_risk_alerts": self.metrics.get("high_risk_alerts", TimeSeriesMetric("", "")).get_window_stats(window),
                "critical_alerts": self.metrics.get("critical_alerts", TimeSeriesMetric("", "")).get_window_stats(window),
                "unique_attackers": self.metrics.get("unique_attackers", TimeSeriesMetric("", "")).get_latest(),
                "unique_targets": self.metrics.get("unique_targets", TimeSeriesMetric("", "")).get_latest(),
            }


# Global monitoring instance
monitoring_system = MonitoringSystem()


# Example usage:
#
# monitoring = monitoring_system
# monitoring.record_flow(is_attack=True, source_ip="1.2.3.4", dest_ip="5.6.7.8", latency_ms=5.2)
# monitoring.record_alert("CRITICAL", "1.2.3.4", "5.6.7.8")
# monitoring.record_inference_latency(4.5)
# monitoring.record_system_health(cpu=45.2, memory_mb=512, model_healthy=True)
#
# dashboard = monitoring.get_dashboard_data()
# print(dashboard["attack_traffic"]["1h"])