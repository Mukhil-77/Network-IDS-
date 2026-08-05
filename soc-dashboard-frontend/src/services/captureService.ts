import { apiClient } from "./apiClient";

export interface CaptureStatus {
  running: boolean;
  interface: string | null;
  backend: string | null;
  active_flows: number;
}

export const captureService = {
  start: async (interfaceName?: string, backend = "scapy", bpfFilter?: string): Promise<{message: string}> => {
    const { data } = await apiClient.post("/capture/start", {
      interface: interfaceName || null,
      backend,
      bpf_filter: bpfFilter || null,
    });
    return data;
  },
  
  stop: async (): Promise<{message: string}> => {
    const { data } = await apiClient.post("/capture/stop");
    return data;
  },
  
  status: async (): Promise<CaptureStatus> => {
    const { data } = await apiClient.get<CaptureStatus>("/capture/status");
    return data;
  },
  
  interfaces: async (): Promise<string[]> => {
    const { data } = await apiClient.get<string[]>("/capture/interfaces");
    return data;
  },
};
