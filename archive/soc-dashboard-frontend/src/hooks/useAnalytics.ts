import { useQuery } from "@tanstack/react-query";
import { analyticsService } from "../services/analyticsService";

export function useAnalyticsOverview(timelineDays = 30) {
  return useQuery({
    queryKey: ["analytics", "overview", timelineDays],
    queryFn: () => analyticsService.getOverview(timelineDays),
  });
}

export function useAnalyticsTrends(timelineDays = 30, forecastDays = 7) {
  return useQuery({
    queryKey: ["analytics", "trends", timelineDays, forecastDays],
    queryFn: () => analyticsService.getTrends(timelineDays, forecastDays),
  });
}
