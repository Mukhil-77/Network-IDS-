import { apiClient } from "./apiClient";
import type { AlertFilters, AlertRow, PaginatedAlerts } from "../types/alert";

// Every function here maps 1:1 onto an endpoint in
// backend/api/routes/alerts.py - no client-side logic beyond building the
// query string, matching what that router actually accepts.
export const alertsService = {
  list: async (filters: AlertFilters): Promise<PaginatedAlerts> => {
    const { data } = await apiClient.get<PaginatedAlerts>("/alerts", { params: filters });
    return data;
  },

  getById: async (id: string): Promise<AlertRow> => {
    const { data } = await apiClient.get<AlertRow>(`/alerts/${id}`);
    return data;
  },

  latest: async (limit = 20): Promise<AlertRow[]> => {
    const { data } = await apiClient.get<AlertRow[]>("/alerts/latest", { params: { limit } });
    return data;
  },
};
