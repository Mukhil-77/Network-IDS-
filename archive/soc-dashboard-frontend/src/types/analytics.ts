export interface AnalyticsOverview {
  top_attack_types: Record<string, number>;
  attack_timeline: { date: string; count: number }[];
  top_source_ips: { source_ip: string; count: number }[];
  top_destination_ips: { destination_ip: string; count: number }[];
  attack_heatmap: { day_of_week: number; hour: number; count: number }[];
  severity_distribution: Record<string, number>;
  detection_accuracy: number | null;
  false_positive_rate: number | null;
  average_detection_time_ms: number;
  average_response_time_seconds: number | null;
}

export interface AnalyticsTrends {
  attack_timeline: { date: string; count: number }[];
  forecast: { date: string; count: number }[];
}
