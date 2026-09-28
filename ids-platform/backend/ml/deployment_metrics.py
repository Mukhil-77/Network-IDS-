"""
Real-Time Deployment Evaluation Metrics

Measures actual operational performance of the IDS in production:
- Inference latency (P50, P95, P99)
- Throughput (flows/sec)
- CPU/Memory usage
- Alert generation latency
- Model loading/startup time
- Detection accuracy over time
- False positive/negative rates in production

Designed for continuous monitoring in production deployments.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Callable
from collections import deque, defaultdict
from threading import Lock
import time
import statistics

import numpy as np
import psutil

from backend.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class LatencyMetrics:
    """Latency statistics."""
    p50: float  # milliseconds
    p95: float
    p99: float
    mean: float
    max: float
    min: float
    count: int
    
    def to_dict(self) -> dict:
        return {
            "p50_ms": round(self.p50, 2),
            "p95_ms": round(self.p95, 2),
            "p99_ms": round(self.p99, 2),
            "mean_ms": round(self.mean, 2),
            "max_ms": round(self.max, 2),
            "min_ms": round(self.min, 2),
            "count": self.count,
        }


@dataclass
class ThroughputMetrics:
    """Throughput statistics."""
    flows_per_second: float
    packets_per_second: float
    bytes_per_second: float
    alerts_per_minute: float
    
    def to_dict(self) -> dict:
        return {
            "flows_per_second": round(self.flows_per_second, 2),
            "packets_per_second": round(self.packets_per_second, 2),
            "bytes_per_second": round(self.bytes_per_second, 2),
            "alerts_per_minute": round(self.alerts_per_minute, 2),
        }


@dataclass
class SystemMetrics:
    """System resource metrics."""
    cpu_percent: float
    memory_mb: float
    memory_percent: float
    disk_io_read_mb: float
    disk_io_write_mb: float
    network_sent_mb: float
    network_recv_mb: float
    
    def to_dict(self) -> dict:
        return {
            "cpu_percent": round(self.cpu_percent, 1),
            "memory_mb": round(self.memory_mb, 1),
            "memory_percent": round(self.memory_percent, 1),
            "disk_io_read_mb": round(self.disk_io_read_mb, 2),
            "disk_io_write_mb": round(self.disk_io_write_mb, 2),
            "network_sent_mb": round(self.network_sent_mb, 2),
            "network_recv_mb": round(self.network_recv_mb, 2),
        }


@dataclass
class DetectionMetrics:
    """Detection performance metrics."""
    total_predictions: int
    alerts_generated: int
    true_positives: int = 0
    false_positives: int = 0
    true_negatives: int = 0
    false_negatives: int = 0
    accuracy: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    fpr: float = 0.0
    fnr: float = 0.0
    avg_confidence: float = 0.0
    avg_latency_ms: float = 0.0
    
    def to_dict(self) -> dict:
        return {
            "total_predictions": self.total_predictions,
            "alerts_generated": self.alerts_generated,
            "true_positives": self.true_positives,
            "false_positives": self.false_positives,
            "true_negatives": self.true_negatives,
            "false_negatives": self.false_negatives,
            "accuracy": round(self.accuracy, 4),
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1": round(self.f1, 4),
            "fpr": round(self.fpr, 4),
            "fnr": round(self.fnr, 4),
            "avg_confidence": round(self.avg_confidence, 2),
            "avg_latency_ms": round(self.avg_latency_ms, 2),
        }


@dataclass
class DeploymentMetrics:
    """Complete deployment evaluation snapshot."""
    timestamp: datetime
    latency: LatencyMetrics
    throughput: ThroughputMetrics
    system: SystemMetrics
    detection: DetectionMetrics
    model_load_time_ms: float = 0.0
    uptime_seconds: float = 0.0
    
    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "latency": self.latency.to_dict(),
            "throughput": self.throughput.to_dict(),
            "system": self.system.to_dict(),
            "detection": self.detection.to_dict(),
            "model_load_time_ms": round(self.model_load_time_ms, 2),
            "uptime_seconds": round(self.uptime_seconds, 1),
        }


class LatencyTracker:
    """Tracks inference latency with percentile computation."""
    
    def __init__(self, max_samples: int = 10000):
        self.max_samples = max_samples
        self._latencies: deque = deque(maxlen=max_samples)
        self._lock = Lock()
    
    def record(self, latency_ms: float):
        """Record a latency measurement."""
        with self._lock:
            self._latencies.append(latency_ms)
    
    def get_metrics(self) -> LatencyMetrics:
        """Compute latency statistics."""
        with self._lock:
            if not self._latencies:
                return LatencyMetrics(0, 0, 0, 0, 0, 0, 0)
            
            latencies = sorted(self._latencies)
            count = len(latencies)
            
            return LatencyMetrics(
                p50=latencies[int(count * 0.50)],
                p95=latencies[int(count * 0.95)],
                p99=latencies[int(count * 0.99)],
                mean=statistics.mean(latencies),
                max=max(latencies),
                min=min(latencies),
                count=count,
            )


class ThroughputTracker:
    """Tracks processing throughput."""
    
    def __init__(self, window_seconds: int = 60):
        self.window_seconds = window_seconds
        self._flows: deque = deque()  # (timestamp, flow_count)
        self._packets: deque = deque()  # (timestamp, packet_count)
        self._bytes: deque = deque()  # (timestamp, byte_count)
        self._alerts: deque = deque()  # (timestamp, alert_count)
        self._lock = Lock()
    
    def record_flow(self, flow_count: int = 1, packet_count: int = 0, byte_count: int = 0):
        """Record a flow."""
        now = time.time()
        with self._lock:
            self._flows.append((now, flow_count))
            self._packets.append((now, packet_count))
            self._bytes.append((now, byte_count))
            self._prune()
    
    def record_alert(self):
        """Record an alert."""
        now = time.time()
        with self._lock:
            self._alerts.append((now, 1))
            self._prune()
    
    def _prune(self):
        """Remove old entries outside the window."""
        cutoff = time.time() - self.window_seconds
        for dq in [self._flows, self._packets, self._bytes, self._alerts]:
            while dq and dq[0][0] < cutoff:
                dq.popleft()
    
    def get_metrics(self) -> ThroughputMetrics:
        """Compute throughput metrics."""
        with self._lock:
            self._prune()
            
            if not self._flows:
                return ThroughputMetrics(0, 0, 0, 0)
            
            window = self.window_seconds
            flow_rate = sum(c for _, c in self._flows) / window
            packet_rate = sum(c for _, c in self._packets) / window
            byte_rate = sum(c for _, c in self._bytes) / window
            alert_rate = sum(c for _, c in self._alerts) / window * 60  # per minute
            
            return ThroughputMetrics(
                flows_per_second=flow_rate,
                packets_per_second=packet_rate,
                bytes_per_second=byte_rate,
                alerts_per_minute=alert_rate,
            )


class SystemMonitor:
    """Monitors system resources."""
    
    def __init__(self):
        self._process = psutil.Process()
        self._last_disk = psutil.disk_io_counters()
        self._last_net = psutil.net_io_counters()
        self._last_time = time.time()
    
    def get_metrics(self) -> SystemMetrics:
        """Get current system metrics."""
        now = time.time()
        cpu = self._process.cpu_percent()
        mem = self._process.memory_info()
        mem_percent = self._process.memory_percent()
        
        # Disk I/O
        disk = psutil.disk_io_counters()
        if self._last_disk:
            disk_read = (disk.read_bytes - self._last_disk.read_bytes) / (1024 * 1024)
            disk_write = (disk.write_bytes - self._last_disk.write_bytes) / (1024 * 1024)
        else:
            disk_read = disk_write = 0.0
        self._last_disk = disk
        
        # Network I/O
        net = psutil.net_io_counters()
        if self._last_net:
            net_sent = (net.bytes_sent - self._last_net.bytes_sent) / (1024 * 1024)
            net_recv = (net.bytes_recv - self._last_net.bytes_recv) / (1024 * 1024)
        else:
            net_sent = net_recv = 0.0
        self._last_net = net
        
        self._last_time = now
        
        return SystemMetrics(
            cpu_percent=cpu,
            memory_mb=mem.rss / (1024 * 1024),
            memory_percent=mem_percent,
            disk_io_read_mb=disk_read,
            disk_io_write_mb=disk_write,
            network_sent_mb=net_sent,
            network_recv_mb=net_recv,
        )


class DeploymentEvaluator:
    """
    Comprehensive deployment evaluation for production IDS.
    
    Tracks:
    - Inference latency (P50, P95, P99)
    - Throughput (flows, packets, bytes, alerts per second)
    - System resources (CPU, memory, disk, network)
    - Detection performance (accuracy, precision, recall, F1, FPR, FNR)
    - Model loading time and uptime
    """
    
    def __init__(
        self,
        model: Any = None,
        window_seconds: int = 60,
        max_latency_samples: int = 10000,
    ):
        self.model = model
        self.window_seconds = window_seconds
        self.start_time = time.time()
        self.model_load_time = 0.0
        
        # Trackers
        self.latency_tracker = LatencyTracker()
        self.throughput_tracker = ThroughputTracker(window_seconds=60)
        self.system_monitor = SystemMonitor()
        
        # Detection tracking
        self._predictions = 0
        self._alerts = 0
        self._tp = self._fp = self._tn = self._fn = 0
        self._confidences = []
        self._prediction_latencies = []
        
        # Ground truth tracking (when labels available)
        self._ground_truth: dict[str, str] = {}  # flow_id -> label
        
        self._lock = Lock()
        self.start_time = time.time()
    
    def record_prediction(
        self,
        flow_id: str,
        prediction: str,
        confidence: float,
        latency_ms: float,
        ground_truth: str = None,
    ):
        """Record a prediction for metrics."""
        with Lock():
            self._predictions += 1
            self._confidences.append(confidence)
            self._prediction_latencies.append(latency_ms)
            
            if ground_truth:
                self._ground_truth[flow_id] = ground_truth
                
                if prediction == ground_truth:
                    if prediction != "BENIGN":
                        self._tp += 1
                    else:
                        self._tn += 1
                else:
                    if prediction != "BENIGN":
                        self._fp += 1
                    else:
                        self._fn += 1
            
            if prediction != "BENIGN":
                self._alerts += 1
        
        # Record latency
        self.latency_tracker.record(latency_ms)
        
        # Record flow
        self.throughput_tracker.record_flow()
    
    def record_flow(self, packet_count: int = 0, byte_count: int = 0):
        """Record a network flow."""
        self.throughput_tracker.record_flow(packet_count=packet_count, byte_count=byte_count)
    
    def record_alert(self):
        """Record an alert."""
        self.throughput_tracker.record_alert()
    
    def record_model_load(self, load_time_ms: float):
        """Record model loading time."""
        self.model_load_time = load_time_ms
    
    def get_deployment_metrics(self) -> DeploymentMetrics:
        """Get complete deployment metrics snapshot."""
        # Latency
        latency = self.latency_tracker.get_metrics()
        
        # Throughput
        throughput = self.throughput_tracker.get_metrics()
        
        # System
        system = self.system_monitor.get_metrics()
        
        # Detection
        detection = self._compute_detection_metrics()
        
        # Uptime
        uptime = time.time() - self.start_time
        
        return DeploymentMetrics(
            timestamp=datetime.now(timezone.utc),
            latency=latency,
            throughput=throughput,
            system=system,
            detection=detection,
            model_load_time_ms=self.model_load_time,
            uptime_seconds=time.time() - self.start_time,
        )
    
    def _compute_detection_metrics(self) -> DetectionMetrics:
        """Compute detection performance metrics."""
        total = self._tp + self._fp + self._tn + self._fn
        
        if total == 0:
            return DetectionMetrics(total_predictions=self._predictions, alerts_generated=self._alerts)
        
        accuracy = (self._tp + self._tn) / total
        precision = self._tp / (self._tp + self._fp) if (self._tp + self._fp) > 0 else 0
        recall = self._tp / (self._tp + self._fn) if (self._tp + self._fn) > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
        fpr = self._fp / (self._fp + self._tn) if (self._fp + self._tn) > 0 else 0
        fnr = self._fn / (self._fn + self._tp) if (self._fn + self._tp) > 0 else 0
        
        avg_conf = statistics.mean(self._confidences) if self._confidences else 0
        avg_lat = statistics.mean(self._prediction_latencies) if self._prediction_latencies else 0
        
        return DetectionMetrics(
            total_predictions=self._predictions,
            alerts_generated=self._alerts,
            true_positives=self._tp,
            false_positives=self._fp,
            true_negatives=self._tn,
            false_negatives=self._fn,
            accuracy=accuracy,
            precision=precision,
            recall=recall,
            f1=f1,
            fpr=fpr,
            fnr=fnr,
            avg_confidence=avg_conf,
            avg_latency_ms=avg_lat,
        )
    
    def get_dashboard_data(self) -> dict:
        """Get all metrics formatted for dashboard."""
        metrics = self.get_deployment_metrics()
        
        return {
            "timestamp": metrics.timestamp.isoformat(),
            "uptime_seconds": round(metrics.uptime_seconds, 1),
            "model_load_time_ms": round(metrics.model_load_time_ms, 2),
            "latency": metrics.latency.to_dict(),
            "throughput": metrics.throughput.to_dict(),
            "system": metrics.system.to_dict(),
            "detection": metrics.detection.to_dict(),
        }


# Global deployment evaluator instance
deployment_evaluator = DeploymentEvaluator()


def create_deployment_evaluator(model: Any = None) -> DeploymentEvaluator:
    """Factory function to create deployment evaluator."""
    return DeploymentEvaluator(model=model)


if __name__ == "__main__":
    print("Deployment evaluation module loaded successfully")