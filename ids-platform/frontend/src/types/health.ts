// Mirrors backend/api/schemas.py's HealthResponse (GET /health) and
// SystemHealthResponse (GET /system/health) - two distinct, differently
// shaped endpoints, kept as two distinct types rather than merged.

export interface ApiHealth {
  status: string;
  model_status: string;
  version: string;
  uptime_seconds: number;
}

export interface SystemHealth {
  status: string;
  model_status: string;
  model_version: string | null;
  active_flows: number;
  alerts_last_minute: number;
  timestamp: string;
}

// Mirrors backend/api/schemas.py's SystemStatsResponse (GET /system/stats) -
// the OS telemetry "task manager" snapshot.
export interface SystemStats {
  timestamp: number;
  cpu: {
    percent: number;
    logical_count: number;
    physical_count: number;
    per_core_percent: number[];
  };
  memory: {
    total_bytes: number;
    used_bytes: number;
    available_bytes: number;
    percent: number;
    swap_total_bytes: number;
    swap_used_bytes: number;
    swap_percent: number;
  };
  disk: {
    total_bytes: number;
    used_bytes: number;
    free_bytes: number;
    percent: number;
  };
  network: {
    bytes_sent_per_sec: number;
    bytes_recv_per_sec: number;
    packets_sent_per_sec: number;
    packets_recv_per_sec: number;
  };
  process: {
    cpu_percent: number;
    memory_rss_bytes: number;
    threads: number;
  };
  gpu: {
    name: string;
    utilization_percent: number;
    memory_used_mb: number;
    memory_total_mb: number;
  } | null;
}
