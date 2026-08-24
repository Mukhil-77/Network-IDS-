import { useQuery } from "@tanstack/react-query";
import { statisticsService } from "../services/statisticsService";

export function useStatistics(windowMinutes = 60) {
  return useQuery({
    queryKey: ["statistics", windowMinutes],
    queryFn: () => statisticsService.get(windowMinutes),
  });
}

export function useTopAttacks(limit = 10) {
  return useQuery({
    queryKey: ["statistics", "top-attacks", limit],
    queryFn: () => statisticsService.topAttacks(limit),
  });
}
