import { apiClient } from "./apiClient";
import type { ModelInfo } from "../types/model";

export const modelService = {
  getInfo: async (): Promise<ModelInfo> => {
    const { data } = await apiClient.get<ModelInfo>("/model/info");
    return data;
  },
};
