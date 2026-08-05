import { apiClient } from "./apiClient";
import type { ApiHealth, SystemHealth, SystemStats } from "../types/health";

export const healthService = {
  // GET /health (Milestone 4) - fast, no DB write.
  getApiHealth: async (): Promise<ApiHealth> => {
    const { data } = await apiClient.get<ApiHealth>("/health");
    return data;
  },

  // GET /system/health (Milestone 6) - extended, DB-backed, persists a snapshot.
  getSystemHealth: async (): Promise<SystemHealth> => {
    const { data } = await apiClient.get<SystemHealth>("/system/health");
    return data;
  },

  // GET /system/stats - point-in-time OS telemetry (psutil-backed).
  getSystemStats: async (): Promise<SystemStats> => {
    const { data } = await apiClient.get<SystemStats>("/system/stats");
    return data;
  },
};
