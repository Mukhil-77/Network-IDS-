// Mirrors backend/api/schemas.py's StatisticsResponse/TopAttackResponse.

export interface ThreatsPerMinutePoint {
  minute: string;
  count: number;
}

export interface TopSourceIP {
  source_ip: string;
  count: number;
}

export interface Statistics {
  threat_count: number;
  threats_per_minute: ThreatsPerMinutePoint[];
  threats_by_type: Record<string, number>;
  threats_by_severity: Record<string, number>;
  top_source_ips: TopSourceIP[];
  // The trained model's own evaluated accuracy (not a live-traffic figure -
  // there's no ground truth for real network traffic). See
  // backend/services/statistics_service.py's docstring.
  detection_accuracy: number | null;
  average_prediction_latency_ms: number;
}

export interface TopAttack {
  attack_type: string;
  total_count: number;
  last_seen: string;
  avg_confidence: number;
}
