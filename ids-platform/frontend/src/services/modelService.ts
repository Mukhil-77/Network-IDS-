import { apiClient } from "./apiClient";
import type { ModelInfo, ModelVersionSummary } from "../types/model";

export const modelService = {
  getInfo: async (): Promise<ModelInfo> => {
    const { data } = await apiClient.get<ModelInfo>("/model/info");
    return data;
  },
  listVersions: async (): Promise<ModelVersionSummary[]> => {
    const { data } = await apiClient.get<ModelVersionSummary[]>("/model/versions");
    return data;
  },
  switchVersion: async (version: string): Promise<ModelInfo> => {
    const { data } = await apiClient.post<ModelInfo>(`/model/switch/${version}`);
    return data;
  },
};