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
