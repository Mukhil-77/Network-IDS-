import { useQuery } from "@tanstack/react-query";
import { statisticsService } from "../services/statisticsService";

export function useStatistics(windowMinutes = 60) {
  return useQuery({
    queryKey: ["statistics", windowMinutes],
    queryFn: () => statisticsService.get(windowMinutes),
    // The dashboard's headline figures must update by themselves while an
    // active capture feeds the detection pipeline - not only on remount.
    refetchInterval: 10_000,
  });
}

export function useTopAttacks(limit = 10) {
  return useQuery({
    queryKey: ["statistics", "top-attacks", limit],
    queryFn: () => statisticsService.topAttacks(limit),
    refetchInterval: 10_000,
  });
}
