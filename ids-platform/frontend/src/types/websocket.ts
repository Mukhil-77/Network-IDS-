// Mirrors backend/websocket/events.py's WSEvent and backend/detection/alert.py's
// Alert schema (the LIVE alert shape pushed over /ws/alerts) - deliberately
// a separate type from AlertRow (types/alert.ts): the live payload lacks
// packet_count/bytes/status, since those are added only when AlertService
// persists a detection (backend/services/alert_service.py), after the
// WebSocket broadcast has already been scheduled.

export interface LiveAlertPayload {
  id: string;
  timestamp: string;
  attack: string;
  severity: string;
  confidence: number;
  source_ip: string;
  destination_ip: string;
  protocol: string;
  flow_id: string;
  source_port: number;
  destination_port: number;
  model_version: string;
}

// Mirrors backend/services/capture_service.py's _packet_payload() - the shape
// broadcast over /ws/alerts as a WSEvent(type="packet") for every parsed
// packet while detection is running. No id: packets are ephemeral, so the
// client assigns its own render key.
export interface LivePacketPayload {
  timestamp: string;
  src_ip: string;
  dst_ip: string;
  src_port: number;
  dst_port: number;
  protocol: string;
  length: number;
  flags: string[];
}

export interface WSEvent {
  type: "alert" | "packet" | "response_started" | "response_completed" | "response_failed" | "rollback_completed";
  payload: LiveAlertPayload | LivePacketPayload | ResponsePayload;
  timestamp: string;
}

// Milestone 8: payload shape for response_started/completed/failed/rollback_completed
// events (backend/response_engine/response_service.py's _broadcast() calls).
// Fields vary slightly by event type - all are optional except the ones
// every event includes, so one type covers all four without a union of
// four near-identical shapes.
export interface ResponsePayload {
  response_group_id?: string;
  response_id?: string;
  original_response_id?: string;
  alert_id: string;
  actions?: string[];
  action?: string;
  status?: string;
  message?: string;
  mode?: string;
}
