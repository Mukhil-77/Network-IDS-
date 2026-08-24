import { apiClient as api } from "./apiClient";

export interface SimulateAttackRequest {
  attack_type: string;
  confidence: number;
  source_ip: string;
  destination_ip: string;
  protocol: string;
  severity: string;
}

export interface SimulationHistoryRecord {
  timestamp: string;
  attack_type: string;
  source_ip: string;
  status: string;
  user: string;
}

export const testingService = {
  simulateAttack: async (req: SimulateAttackRequest) => {
    const response = await api.post("/testing/simulate", req);
    return response.data;
  },

  getHistory: async (): Promise<SimulationHistoryRecord[]> => {
    const response = await api.get("/testing/history");
    return response.data;
  },
};
