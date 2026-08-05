// Mirrors backend/api/schemas.py's AlertResponse/PaginatedAlertsResponse exactly.

export type Severity = "Critical" | "High" | "Medium" | "Low";

export interface AlertRow {
  id: string;
  timestamp: string;
  attack_type: string;
  confidence: number;
  severity: string;
  source_ip: string;
  destination_ip: string;
  protocol: string;
  flow_id: string;
  status: string;
  model_version: string;
  // Only populated for alerts fetched via REST (backend/database/models.py's
  // Alert row) - a live WebSocket-pushed alert (see websocket.ts) doesn't
  // carry these, since backend/detection/alert.py's Alert schema predates
  // persistence and only has what the detection pipeline itself produces.
  packet_count?: number;
  bytes?: number;
  processing_time_ms?: number;
}

export interface PaginatedAlerts {
  items: AlertRow[];
  total: number;
  page: number;
  page_size: number;
}

export interface AlertFilters {
  start_date?: string;
  end_date?: string;
  attack_type?: string;
  severity?: string;
  source_ip?: string;
  destination_ip?: string;
  min_confidence?: number;
  page?: number;
  page_size?: number;
  sort_by?: "timestamp" | "confidence" | "severity";
  sort_desc?: boolean;
}
