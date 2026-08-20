import { useQuery } from "@tanstack/react-query";
import { flowsService } from "../services/flowsService";
import type { FlowFilters } from "../types/flow";

export function useFlows(filters: FlowFilters) {
  return useQuery({
    queryKey: ["flows", filters],
    queryFn: () => flowsService.list(filters),
    placeholderData: (previous) => previous,
  });
}

export function useFlowSummary() {
  return useQuery({
    queryKey: ["flows", "summary"],
    queryFn: flowsService.summary,
    placeholderData: (previous) => previous,
  });
}