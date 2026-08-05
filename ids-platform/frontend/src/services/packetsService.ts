import { apiClient } from "./apiClient";
import type { LivePacketPayload } from "../types/websocket";

// GET /detection/packets/recent - the bounded in-memory history of packets
// the capture pipeline has seen (populated only while detection is running,
// since it's driven by live capture).
export const packetsService = {
  getRecent: async (limit = 100): Promise<LivePacketPayload[]> => {
    const { data } = await apiClient.get<LivePacketPayload[]>("/detection/packets/recent", { params: { limit } });
    return data;
  },
};
