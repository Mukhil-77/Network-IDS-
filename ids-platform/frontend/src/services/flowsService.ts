import { apiClient } from "./apiClient";
import type { FlowFilters, FlowSummary, PaginatedFlows } from "../types/flow";

export const flowsService = {
  list: async (filters: FlowFilters): Promise<PaginatedFlows> => {
    const { data } = await apiClient.get<PaginatedFlows>("/flows", { params: filters });
    return data;
  },
  summary: async (): Promise<FlowSummary> => {
    const { data } = await apiClient.get<FlowSummary>("/flows/summary");
    return data;
  },
};
