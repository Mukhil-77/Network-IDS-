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
