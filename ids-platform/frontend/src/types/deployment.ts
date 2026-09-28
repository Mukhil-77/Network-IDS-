export interface LatencyMetrics {
  p50: number;
  p95: number;
  p99: number;
  mean: number;
  max: number;
  min: number;
  count: number;
}

export interface ThroughputMetrics {
  flows_per_second: number;
  packets_per_second: number;
  bytes_per_second: number;
  alerts_per_minute: number;
}

export interface SystemMetrics {
  cpu_percent: number;
  memory_mb: number;
  memory_percent: number;
  disk_io_read_mb: number;
  disk_io_write_mb: number;
  network_sent_mb: number;
  network_recv_mb: number;
}

export interface DetectionMetrics {
  total_predictions: number;
  alerts_generated: number;
  true_positives: number;
  false_positives: number;
  true_negatives: number;
  false_negatives: number;
  accuracy: number;
  precision: number;
  recall: number;
  f1: number;
  fpr: number;
  fnr: number;
  avg_confidence: number;
  avg_latency_ms: number;
}

export interface DeploymentMetrics {
  timestamp: string;
  latency: LatencyMetrics;
  throughput: ThroughputMetrics;
  system: SystemMetrics;
  detection: DetectionMetrics;
  model_load_time_ms: number;
  uptime_seconds: number;
}