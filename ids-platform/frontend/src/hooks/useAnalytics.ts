import { useQuery } from "@tanstack/react-query";
import { analyticsService } from "../services/analyticsService";

export function useAnalyticsOverview(timelineDays = 30) {
  return useQuery({
    queryKey: ["analytics", "overview", timelineDays],
    queryFn: () => analyticsService.getOverview(timelineDays),
    staleTime: 30000,
    gcTime: 300000,
    placeholderData: (previousData) => previousData,
  });
}

export function useAnalyticsTrends(timelineDays = 30, forecastDays = 7) {
  return useQuery({
    queryKey: ["analytics", "trends", timelineDays, forecastDays],
    queryFn: () => analyticsService.getTrends(timelineDays, forecastDays),
    staleTime: 30000,
    gcTime: 300000,
    placeholderData: (previousData) => previousData,
  });
}