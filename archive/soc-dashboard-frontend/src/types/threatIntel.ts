export interface ThreatIndicator {
  id: string;
  value: string;
  indicator_type: string;
  tag: string;
  source: string;
  confidence: number;
  notes: string | null;
  added_at: string;
}
