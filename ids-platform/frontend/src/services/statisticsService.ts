import { apiClient } from "./apiClient";
import type { Statistics, TopAttack } from "../types/statistics";

export const statisticsService = {
  get: async (windowMinutes = 60): Promise<Statistics> => {
    const { data } = await apiClient.get<Statistics>("/statistics", {
      params: { window_minutes: windowMinutes },
    });
    return data;
  },

  topAttacks: async (limit = 10): Promise<TopAttack[]> => {
    const { data } = await apiClient.get<TopAttack[]>("/attacks/top", { params: { limit } });
    return data;
  },
};
