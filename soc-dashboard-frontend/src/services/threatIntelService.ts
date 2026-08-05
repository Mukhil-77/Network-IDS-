import { apiClient } from "./apiClient";
import type { ThreatIndicator } from "../types/threatIntel";

export const threatIntelService = {
  list: async (tag?: string): Promise<ThreatIndicator[]> => {
    const { data } = await apiClient.get<ThreatIndicator[]>("/threat-intelligence", { params: { tag } });
    return data;
  },
};
