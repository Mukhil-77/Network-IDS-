import { apiClient } from "./apiClient";

// Mirrors backend/api/routes/admin.py's CLEAR_SCOPES keys (labels in English
// for the Settings "Danger Zone" checkboxes).
export const CLEAR_SCOPE_LABELS: { key: string; label: string }[] = [
  { key: "responses", label: "Response history" },
  { key: "incidents", label: "Incidents" },
  { key: "alerts", label: "Alerts" },
  { key: "flows", label: "Flows" },
  { key: "statistics", label: "Attack statistics" },
  { key: "system_health", label: "System health snapshots" },
  { key: "packet_stats", label: "Packet statistics" },
  { key: "audit", label: "Audit log" },
  { key: "threat_intel", label: "Threat indicators" },
  { key: "blocked_ips", label: "Blocked IPs" },
];

export interface ClearDataResponse {
  deleted: Record<string, number>;
}

export interface ResetModelsResponse {
  removed_versions: string[];
  model_metadata_rows_deleted: number;
}

export const adminService = {
  // POST /admin/data/clear - empty scopes = delete everything.
  clearData: async (scopes: string[]): Promise<ClearDataResponse> => {
    const { data } = await apiClient.post<ClearDataResponse>("/admin/data/clear", { scopes });
    return data;
  },

  resetModels: async (): Promise<ResetModelsResponse> => {
    const { data } = await apiClient.post<ResetModelsResponse>("/admin/models/reset");
    return data;
  },
};