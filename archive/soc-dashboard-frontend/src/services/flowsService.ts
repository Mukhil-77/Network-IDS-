import { apiClient } from "./apiClient";
import type { FlowFilters, PaginatedFlows } from "../types/flow";

export const flowsService = {
  list: async (filters: FlowFilters): Promise<PaginatedFlows> => {
    const { data } = await apiClient.get<PaginatedFlows>("/flows", { params: filters });
    return data;
  },
};
