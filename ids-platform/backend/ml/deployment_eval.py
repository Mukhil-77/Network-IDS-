"""
Real-time deployment evaluation for IDS.

Measures operational performance metrics:
- Inference latency (P50, P95, P99)
- Throughput (flows/sec, packets/sec)
- CPU and memory usage
- Startup/model loading time
- Alert generation latency
- End-to-end detection latency

Research contribution: Deployment-aware continuous IDS evaluation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Callable
from collections import deque
import time
import statistics
import threading
import psutil
import os

from backend.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class LatencyMetrics:
    """Latency measurements."""
    p50_ms: float = 0.0
    p95_ms: float = 0.0
    p99_ms: float = 0.0
    mean_ms: float = 0.0
    min_ms: float = 0.0
    max_ms: float = 0.0
    count: int = 0
    
    @classmethod
    def from_samples(cls, samples: List[float]) -> "LatencyMetrics":
        if not samples:
            return cls()
        sorted_samples = sorted(samples)
        n = len(samples)
        return cls(
            p50_ms=sorted_samples[int(0.50 * n)],
            p95_ms=sorted_samples[int(0.95 * n)],
            p99_ms=sorted_samples[int(0.99 * n)],
            mean_ms=statistics.mean(samples),
            min_ms=min(samples),
            max_ms=max(samples),
            count=len(samples),
        )


@dataclass
class ThroughputMetrics:
    """Throughput measurements."""
    flows_per_second: float = 0.0
    packets_per_second: float = 0.0
    bytes_per_second: float = 0.0
    alerts_per_second: float = 0.0
    window_seconds: float = 0.0
    total_flows: int = 0
    total_packets: int = 0
    total_bytes: int = 0
    total_alerts: int = 0


@dataclass
class ResourceMetrics:
    """System resource usage."""
    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    memory_percent: float = 0.0
    disk_io_read_mb_s: float = 0.0
    disk_io_write_mb_s: float = 0.0
    network_io_sent_mb_s: float = 0.0
    network_io_recv_mb_s: float = 0.0
    thread_count: int = 0
    open_fds: int = 0


@dataclass
class DeploymentEvaluationResult:
    """Complete deployment evaluation result."""
    timestamp: datetime
    evaluation_duration_seconds: float
    latency: LatencyMetrics
    throughput: ThroughputMetrics
    resources: ResourceMetrics
    startup_time_seconds: float = 0.0
    model_load_time_seconds: float = 0.0
    model_size_mb: float = 0.0
    sustained_load_test: bool = False
    test_duration_seconds: float = 0.0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class LatencyTracker:
    """Tracks latency measurements with percentile computation."""
    
    def __init__(self, max_samples: int = 10000):
        self.samples: deque = deque(maxlen=max_samples)
        self.lock = threading.Lock()
    
    def record(self, latency_ms: float):
        with self.lock:
            self.samples.append(latency_ms)
    
    def get_metrics(self) -> LatencyMetrics:
        with self.lock:
            return LatencyMetrics.from_samples(list(self.samples))
    
    def reset(self):
        with self.lock:
            self.samples.clear()


class ThroughputTracker:
    """Tracks throughput metrics with sliding window."""
    
    def __init__(self, window_seconds: float = 60.0):
        self.window_seconds = window_seconds
        self.events: deque = deque()  # (timestamp, event_type, count)
        self.lock = threading.Lock()
    
    def record_flow(self, packet_count: int = 1, byte_count: int = 0):
        with self.lock:
            now = time.time()
            self.events.append((now, "flow", packet_count, byte_count))
            self._cleanup(now)
    
    def record_packet(self, byte_count: int):
        with self.lock:
            now = time.time()
            self.events.append((now, "packet", 1, byte_count))
            self._cleanup(now)
    
    def record_alert(self):
        with self.lock:
            now = time.time()
            self.events.append((now, "alert", 1, 0))
            self._cleanup(now)
    
    def _cleanup(self, now: float):
        cutoff = now - self.window_seconds
        while self.events and self.events[0][0] < cutoff:
            self.events.popleft()
    
    def get_metrics(self) -> ThroughputMetrics:
        with self.lock:
            if not self.events:
                return ThroughputMetrics(window_seconds=self.window_seconds)
            
            now = time.time()
            cutoff = now - self.window_seconds
            recent = [e for e in self.events if e[0] >= cutoff]
            
            if not recent:
                return ThroughputMetrics(window_seconds=self.window_seconds)
            
            flow_count = sum(e[2] for e in recent if e[1] == "flow")
            packet_count = sum(e[2] for e in recent if e[1] == "packet")
            byte_count = sum(e[3] for e in recent if e[1] in ("flow", "packet"))
            alert_count = sum(1 for e in recent if e[1] == "alert")
            
            duration = min(self.window_seconds, now - recent[0][0]) if recent else self.window_seconds
            
            return ThroughputMetrics(
                flows_per_second=flow_count / duration,
                packets_per_second=packet_count / duration,
                bytes_per_second=byte_count / duration,
                alerts_per_second=alert_count / duration,
                window_seconds=duration,
                total_flows=sum(1 for e in self.events if e[1] == "flow"),
                total_packets=sum(e[2] for e in self.events if e[1] == "packet"),
                total_bytes=sum(e[3] for e in self.events),
                total_alerts=sum(1 for e in self.events if e[1] == "alert"),
            )


class ResourceMonitor:
    """Monitors system resource usage."""
    
    def __init__(self, pid: Optional[int] = None):
        self.pid = pid or os.getpid()
        self.process = psutil.Process(self.pid)
        self._last_disk_io = None
        self._last_network_io = None
        self._last_time = None
    
    def get_metrics(self) -> ResourceMetrics:
        try:
            # CPU and memory
            cpu = self.process.cpu_percent(interval=0.1)
            mem_info = self.process.memory_info()
            mem_percent = self.process.memory_percent()
            
            # Disk I/O
            disk_io = self.process.io_counters()
            disk_read_mb_s = 0.0
            disk_write_mb_s = 0.0
            if self._last_disk_io and self._last_time:
                dt = time.time() - self._last_time
                if dt > 0:
                    disk_read_mb_s = (disk_io.read_bytes - self._last_disk_io.read_bytes) / dt / (1024 * 1024)
                    disk_write_mb_s = (disk_io.write_bytes - self._last_disk_io.write_bytes) / dt / (1024 * 1024)
            
            # Network I/O (system-wide)
            net_io = psutil.net_io_counters()
            net_sent_mb_s = 0.0
            net_recv_mb_s = 0.0
            if self._last_network_io and self._last_time:
                dt = time.time() - self._last_time
                if dt > 0:
                    net_sent_mb_s = (net_io.bytes_sent - self._last_network_io.bytes_sent) / dt / (1024 * 1024)
                    net_recv_mb_s = (net_io.bytes_recv - self._last_network_io.bytes_recv) / dt / (1024 * 1024)
            
            # Update last values
            self._last_disk_io = disk_io
            self._last_network_io = net_io
            self._last_time = time.time()
            
            return ResourceMetrics(
                cpu_percent=cpu,
                memory_mb=mem_info.rss / (1024 * 1024),
                memory_percent=mem_percent,
                disk_io_read_mb_s=disk_read_mb_s,
                disk_io_write_mb_s=disk_write_mb_s,
                network_io_sent_mb_s=net_sent_mb_s,
                network_io_recv_mb_s=net_recv_mb_s,
                thread_count=self.process.num_threads(),
                open_fds=self.process.num_fds() if hasattr(self.process, 'num_fds') else 0,
            )
        except Exception as e:
            logger.warning(f"Failed to get resource metrics: {e}")
            return ResourceMetrics()


class DeploymentEvaluator:
    """
    Comprehensive deployment evaluation for IDS.
    
    Runs sustained load tests and measures all operational metrics.
    """
    
    def __init__(
        self,
        model: Any = None,
        inference_fn: Optional[Callable] = None,
        sample_data: Optional[np.ndarray] = None,
    ):
        self.model = model
        self.inference_fn = inference_fn or (lambda x: model.predict(x) if model else None)
        self.sample_data = sample_data
        
        self.latency_tracker = LatencyTracker()
        self.throughput_tracker = ThroughputTracker()
        self.resource_monitor = ResourceMonitor()
        
        self.start_time: Optional[float] = None
        self.model_load_start: Optional[float] = None
        self.model_load_end: Optional[float] = None
        self.evaluation_start: Optional[float] = None
        self.evaluation_end: Optional[float] = None
    
    def start_evaluation(self):
        """Start evaluation."""
        self.evaluation_start = time.time()
        if self.model_load_start is None:
            self.model_load_start = time.time()
    
    def record_model_loaded(self):
        """Record model load completion."""
        self.model_load_end = time.time()
    
    def run_inference_benchmark(
        self, 
        n_iterations: int = 1000,
        batch_size: int = 1,
        warmup_iterations: int = 100,
    ) -> LatencyMetrics:
        """
        Run inference latency benchmark.
        
        Args:
            n_iterations: Number of inference iterations
            batch_size: Batch size for inference
            warmup_iterations: Warmup iterations (not counted)
            
        Returns:
            LatencyMetrics with percentile statistics
        """
        if not self.inference_fn:
            raise ValueError("No inference function available")
        
        # Warmup
        if self.sample_data is not None:
            for _ in range(warmup_iterations):
                _ = self.inference_fn(self.sample_data[:batch_size])
        
        # Benchmark
        latencies = []
        for _ in range(n_iterations):
            start = time.perf_counter()
            _ = self.inference_fn(self.sample_data[:batch_size])
            elapsed_ms = (time.perf_counter() - start) * 1000
            latencies.append(elapsed_ms)
            self.latency_tracker.record(elapsed_ms)
        
        return LatencyMetrics.from_samples(latencies)
    
    def run_sustained_load_test(
        self,
        duration_seconds: float = 60.0,
        target_flows_per_second: float = 1000.0,
        batch_size: int = 32,
    ) -> DeploymentEvaluationResult:
        """
        Run sustained load test.
        
        Simulates sustained traffic at target rate and measures all metrics.
        """
        self.start_evaluation()
        
        if self.model_load_start and self.model_load_end:
            model_load_time = self.model_load_end - self.model_load_start
        else:
            model_load_time = 0.0
        
        start_time = time.time()
        end_time = start_time + duration_seconds
        
        interval = 1.0 / target_flows_per_second
        batch_interval = interval * batch_size
        
        latencies = []
        flow_count = 0
        packet_count = 0
        byte_count = 0
        alert_count = 0
        errors = []
        warnings = []
        
        next_batch_time = time.time()
        
        while time.time() < end_time:
            batch_start = time.perf_counter()
            
            try:
                # Run batch inference
                if self.sample_data is not None and self.inference_fn:
                    batch_data = self.sample_data[:batch_size]
                    batch_start_time = time.perf_counter()
                    predictions = self.inference_fn(batch_data)
                    inference_ms = (time.perf_counter() - batch_start_time) * 1000
                    latencies.append(inference_ms)
                    self.latency_tracker.record(inference_ms)
                    
                    # Simulate flow processing
                    flow_count += batch_size
                    packet_count += batch_size * 10  # approx 10 packets per flow
                    byte_count += batch_size * 1500  # approx 1500 bytes per flow
                    
                    # Count alerts (simplified)
                    if hasattr(self.model, 'predict'):
                        preds = self.model.predict(self.sample_data[:batch_size])
                        alert_count += sum(1 for p in preds if p != "BENIGN")
                
                self.throughput_tracker.record_flow(batch_size, batch_size * 1500)
                
            except Exception as e:
                errors.append(f"Batch error: {e}")
            
            # Rate limiting
            elapsed = time.perf_counter() - batch_start
            sleep_time = max(0, batch_interval - elapsed)
            if sleep_time > 0:
                time.sleep(sleep_time)
        
        self.evaluation_end = time.time()
        
        # Collect final metrics
        latency_metrics = LatencyMetrics.from_samples(latencies)
        throughput_metrics = self.throughput_tracker.get_metrics()
        resource_metrics = self.resource_monitor.get_metrics()
        
        return DeploymentEvaluationResult(
            timestamp=datetime.now(),
            evaluation_duration_seconds=duration_seconds,
            latency=latency_metrics,
            throughput=throughput_metrics,
            resources=resource_metrics,
            startup_time_seconds=self.evaluation_end - self.evaluation_start if self.evaluation_start else 0,
            model_load_time_seconds=model_load_time,
            sustained_load_test=True,
            test_duration_seconds=duration_seconds,
            errors=errors,
            warnings=warnings,
        )
    
    def get_current_metrics(self) -> Dict[str, Any]:
        """Get current operational metrics."""
        return {
            "latency": self.latency_tracker.get_metrics().__dict__,
            "throughput": self.throughput_tracker.get_metrics().__dict__,
            "resources": self.resource_monitor.get_metrics().__dict__,
        }
    
    def generate_report(self, result: DeploymentEvaluationResult) -> str:
        """Generate a text report from evaluation result."""
        report = []
        report.append("=" * 60)
        report.append("DEPLOYMENT EVALUATION REPORT")
        report.append("=" * 60)
        report.append(f"Timestamp: {result.timestamp.isoformat()}")
        report.append(f"Evaluation Duration: {result.evaluation_duration_seconds:.1f}s")
        report.append(f"Model Load Time: {result.model_load_time_seconds:.2f}s")
        report.append("")
        
        report.append("LATENCY METRICS:")
        report.append(f"  P50: {result.latency.p50_ms:.2f} ms")
        report.append(f"  P95: {result.latency.p95_ms:.2f} ms")
        report.append(f"  P99: {result.latency.p99_ms:.2f} ms")
        report.append(f"  Mean: {result.latency.mean_ms:.2f} ms")
        report.append(f"  Min: {result.latency.min_ms:.2f} ms")
        report.append(f"  Max: {result.latency.max_ms:.2f} ms")
        report.append(f"  Samples: {result.latency.count}")
        report.append("")
        
        report.append("THROUGHPUT METRICS:")
        report.append(f"  Flows/sec: {result.throughput.flows_per_second:.2f}")
        report.append(f"  Packets/sec: {result.throughput.packets_per_second:.2f}")
        report.append(f"  Bytes/sec: {result.throughput.bytes_per_second:.2f}")
        report.append(f"  Alerts/sec: {result.throughput.alerts_per_second:.2f}")
        report.append(f"  Window: {result.throughput.window_seconds:.1f}s")
        report.append("")
        
        report.append("RESOURCE METRICS:")
        report.append(f"  CPU: {result.resources.cpu_percent:.1f}%")
        report.append(f"  Memory: {result.resources.memory_mb:.1f} MB ({result.resources.memory_percent:.1f}%)")
        report.append(f"  Threads: {result.resources.thread_count}")
        report.append(f"  Open FDs: {result.resources.open_fds}")
        report.append(f"  Disk Read: {result.resources.disk_io_read_mb_s:.2f} MB/s")
        report.append(f"  Disk Write: {result.resources.disk_io_write_mb_s:.2f} MB/s")
        report.append("")
        
        if result.errors:
            report.append("ERRORS:")
            for err in result.errors:
                report.append(f"  - {err}")
        
        if result.warnings:
            report.append("WARNINGS:")
            for warn in result.warnings:
                report.append(f"  - {warn}")
        
        return "\n".join(report)


# Global evaluator instance
deployment_evaluator = DeploymentEvaluator()


# Example usage:
#
# from backend.ml.deployment_eval import DeploymentEvaluator, deployment_evaluator
# from sklearn.ensemble import RandomForestClassifier
# import numpy as np
#
# # Setup
# model = RandomForestClassifier()
# X_sample = np.random.randn(1000, 35)  # 35 PCA features
# evaluator = DeploymentEvaluator(model=model, sample_data=X_sample)
#
# # Run benchmark
# evaluator.start_evaluation()
# evaluator.record_model_loaded()
# latency = evaluator.run_inference_benchmark(n_iterations=1000)
# print(f"P50: {latency.p50_ms:.2f}ms, P95: {latency.p95_ms:.2f}ms")
#
# # Run sustained load test
# result = evaluator.run_sustained_load_test(duration_seconds=60, target_flows_per_second=1000)
# print(deployment_evaluator.generate_report(result))