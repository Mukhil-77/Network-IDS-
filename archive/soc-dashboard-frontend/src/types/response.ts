// Mirrors backend/api/schemas.py's response-engine schemas exactly (Milestone 8).

export interface ResponseHistoryEntry {
  id: string;
  response_group_id: string;
  alert_id: string;
  action: string;
  status: string;
  message: string | null;
  execution_time_ms: number;
  operator: string;
  mode: string;
  rollback_available: boolean;
  rolled_back: boolean;
  timestamp: string;
}

export interface PaginatedResponses {
  items: ResponseHistoryEntry[];
  total: number;
  page: number;
  page_size: number;
}

export interface ResponseFilters {
  alert_id?: string;
  status?: string;
  mode?: string;
  action?: string;
  page?: number;
  page_size?: number;
}

export interface ResponseExecuteRequest {
  alert_id: string;
  actions?: string[];
  mode?: "simulation" | "live";
  operator?: string;
}

export interface ResponseRulesConfig {
  simulation_mode: boolean;
  policies: Record<string, string[]>;
  available_actions: string[];
}
