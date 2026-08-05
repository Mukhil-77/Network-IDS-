export interface TimelineEntry {
  timestamp: string;
  actor: string;
  action: string;
  note: string;
}

export interface Incident {
  id: string;
  title: string;
  description: string;
  severity: string;
  priority: string;
  status: string;
  owner: string | null;
  alert_id: string | null;
  timeline: TimelineEntry[];
  created_by: string;
  created_at: string;
  updated_at: string;
  closed_at: string | null;
}

export interface PaginatedIncidents {
  items: Incident[];
  total: number;
  page: number;
  page_size: number;
}

export interface IncidentFilters {
  status?: string;
  severity?: string;
  owner?: string;
  page?: number;
  page_size?: number;
}

export interface IncidentCreateRequest {
  title: string;
  description?: string;
  severity: string;
  priority?: string;
  alert_id?: string;
}

export interface IncidentUpdateRequest {
  status?: string;
  owner?: string;
  priority?: string;
  note?: string;
}
