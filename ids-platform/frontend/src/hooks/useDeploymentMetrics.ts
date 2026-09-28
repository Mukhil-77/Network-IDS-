import { useQuery } from "@tanstack/react-query";
import { apiClient } from "../services/apiClient";
import type { DeploymentMetrics } from "../types/deployment";

export function useDeploymentMetrics() {
  return useQuery<DeploymentMetrics>({
    queryKey: ["deployment", "metrics"],
    queryFn: async () => {
      const { data } = await apiClient.get<DeploymentMetrics>("/deployment/metrics");
      return data;
    },
    refetchInterval: 30_000,
    staleTime: 10_000,
  });
}