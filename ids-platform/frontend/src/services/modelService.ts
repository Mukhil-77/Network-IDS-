import { apiClient } from "./apiClient";
import type { ModelInfo, ModelTrainStatus, ModelVersionSummary } from "../types/model";

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
  train: async (algorithm: string): Promise<ModelTrainStatus> => {
    const { data } = await apiClient.post<ModelTrainStatus>("/model/train", { algorithm });
    return data;
  },
  trainStatus: async (): Promise<ModelTrainStatus> => {
    const { data } = await apiClient.get<ModelTrainStatus>("/model/train/status");
    return data;
  },
  cancelTrain: async (): Promise<ModelTrainStatus> => {
    const { data } = await apiClient.post<ModelTrainStatus>("/model/train/cancel");
    return data;
  },
  deleteVersion: async (version: string): Promise<{ removed: string; active_switched: boolean }> => {
    const { data } = await apiClient.delete<{ removed: string; active_switched: boolean }>(`/model/${version}`);
    return data;
  },
};