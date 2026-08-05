import { useQuery } from "@tanstack/react-query";
import { healthService } from "../services/healthService";

export function useApiHealth() {
  return useQuery({
    queryKey: ["health", "api"],
    queryFn: healthService.getApiHealth,
    refetchInterval: 30_000, // the one legitimate poll in this app - a heartbeat, not a data feed
  });
}

export function useSystemHealth() {
  return useQuery({
    queryKey: ["health", "system"],
    queryFn: healthService.getSystemHealth,
    refetchInterval: 30_000,
  });
}

// The task-manager view polls hard (every 2 s) so the gauges/sparklines feel
// live - this is the one feed that actually earns a fast poll interval.
export function useSystemStats() {
  return useQuery({
    queryKey: ["health", "stats"],
    queryFn: healthService.getSystemStats,
    refetchInterval: 2_000,
  });
}
