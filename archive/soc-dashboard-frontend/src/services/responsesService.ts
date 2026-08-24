import { apiClient } from "./apiClient";
import type {
  PaginatedResponses,
  ResponseExecuteRequest,
  ResponseFilters,
  ResponseHistoryEntry,
  ResponseRulesConfig,
} from "../types/response";

export const responsesService = {
  list: async (filters: ResponseFilters): Promise<PaginatedResponses> => {
    const { data } = await apiClient.get<PaginatedResponses>("/responses", { params: filters });
    return data;
  },

  getById: async (id: string): Promise<ResponseHistoryEntry> => {
    const { data } = await apiClient.get<ResponseHistoryEntry>(`/responses/${id}`);
    return data;
  },

  history: async (limit = 20): Promise<ResponseHistoryEntry[]> => {
    const { data } = await apiClient.get<ResponseHistoryEntry[]>("/responses/history", { params: { limit } });
    return data;
  },

  execute: async (request: ResponseExecuteRequest): Promise<ResponseHistoryEntry[]> => {
    const { data } = await apiClient.post<ResponseHistoryEntry[]>("/responses/execute", request);
    return data;
  },

  rollback: async (responseId: string, operator = "analyst"): Promise<ResponseHistoryEntry> => {
    const { data } = await apiClient.post<ResponseHistoryEntry>("/responses/rollback", { response_id: responseId, operator });
    return data;
  },

  getRules: async (): Promise<ResponseRulesConfig> => {
    const { data } = await apiClient.get<ResponseRulesConfig>("/response-rules");
    return data;
  },

  updateRules: async (update: Partial<ResponseRulesConfig>): Promise<ResponseRulesConfig> => {
    const { data } = await apiClient.put<ResponseRulesConfig>("/response-rules", update);
    return data;
  },
};
