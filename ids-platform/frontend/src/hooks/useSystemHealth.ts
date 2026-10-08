import { useQuery } from "@tanstack/react-query";
import { healthService } from "../services/healthService";

export function useApiHealth() {
  return useQuery({
    queryKey: ["health", "api"],
    queryFn: healthService.getApiHealth,
    refetchInterval: 30_000,
    staleTime: 30000,
    gcTime: 300000,
    placeholderData: (previousData) => previousData,
  });
}

export function useSystemHealth() {
  return useQuery({
    queryKey: ["health", "system"],
    queryFn: healthService.getSystemHealth,
    refetchInterval: 30_000,
    staleTime: 30000,
    gcTime: 300000,
    placeholderData: (previousData) => previousData,
  });
}

export function useSystemStats() {
  return useQuery({
    queryKey: ["health", "stats"],
    queryFn: healthService.getSystemStats,
    refetchInterval: 2_000,
    staleTime: 15000,
    gcTime: 300000,
    placeholderData: (previousData) => previousData,
  });
}