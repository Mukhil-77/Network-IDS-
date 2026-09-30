// Mirrors backend/api/schemas.py's AlertResponse/PaginatedAlertsResponse exactly.

export type Severity = "Critical" | "High" | "Medium" | "Low" | "Legitimate" | "Unknown";
export type RiskLevel = "LOW" | "GUARDED" | "MEDIUM" | "HIGH" | "CRITICAL";
export type ThreatTag = "Known Malicious" | "Suspicious" | "Unknown" | "Trusted";
export type AlertPriority = "P1_CRITICAL" | "P2_HIGH" | "P3_MEDIUM" | "P4_LOW";

export interface AlertRow {
  id: string;
  timestamp: string;
  attack_type: string;
  confidence: number;
  severity: Severity;
  risk_score: number;
  risk_level: RiskLevel;
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
  threat_tag: ThreatTag;
  // Prioritization fields
  priority?: AlertPriority;
  priority_score?: number;
  is_grouped?: boolean;
  group_id?: string;
  group_size?: number;
  first_seen?: string;
  last_seen?: string;
  // Explainability (SHAP) - NOT currently provided by backend API.
  // Backend ML has explainability.py but it's not exposed through /alerts endpoints.
  // shap_explanation?: SHAPExplanation;  // Future: uncomment when backend exposes it
}

// SHAP/Explainability types - NOT currently provided by backend API.
// Backend ML has explainability.py and shap_explainer.py but these are not
// exposed through the prediction or alerts API endpoints. Kept for future use.
/*
export interface SHAPExplanation {
  predicted_class: string;
  confidence: number;
  top_features: SHAPFeature[];
  base_value: number;
  prediction_value: number;
}

export interface SHAPFeature {
  feature: string;
  shap_value: number;
  impact: "positive" | "negative" | "unknown";
  magnitude: number;
}
*/

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
  sort_by?: "timestamp" | "confidence" | "severity" | "risk_score" | "priority_score" | "priority";
  sort_desc?: boolean;
  threat_tag?: ThreatTag;
  priority?: AlertPriority;
}
