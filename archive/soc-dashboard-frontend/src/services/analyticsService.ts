import { apiClient } from "./apiClient";
import type { AnalyticsOverview, AnalyticsTrends } from "../types/analytics";

export const analyticsService = {
  getOverview: async (timelineDays = 30): Promise<AnalyticsOverview> => {
    const { data } = await apiClient.get<AnalyticsOverview>("/analytics", { params: { timeline_days: timelineDays } });
    return data;
  },

  getTrends: async (timelineDays = 30, forecastDays = 7): Promise<AnalyticsTrends> => {
    const { data } = await apiClient.get<AnalyticsTrends>("/analytics/trends", {
      params: { timeline_days: timelineDays, forecast_days: forecastDays },
    });
    return data;
  },
};
