import { apiClient } from "./apiClient";

export interface CaptureStatus {
  running: boolean;
  interface: string | null;
  backend: string | null;
  active_flows: number;
  packet_count: number;
  protocols: string[] | null;
  predictions_count: number;
  average_prediction_latency_ms: number;
}

export interface CaptureInterface {
  /** Raw adapter handle scapy binds to, e.g. "\\Device\\NPF_{GUID}". */
  name: string;
  /** Human-readable label for the dropdown, e.g. "Intel(R) Wi-Fi 6 AX201 · NPF_...". */
  description: string;
}

export const captureService = {
  start: async (
    options: {
      interfaceName?: string;
      backend?: string;
      bpfFilter?: string;
      protocols?: string[];
    } = {},
  ): Promise<{ message: string; bpf_filter: string }> => {
    const { data } = await apiClient.post("/capture/start", {
      interface: options.interfaceName || null,
      backend: options.backend || "scapy",
      bpf_filter: options.bpfFilter || null,
      protocols: options.protocols || ["tcp", "udp"],
    });
    return data;
  },

  stop: async (): Promise<{ message: string }> => {
    const { data } = await apiClient.post("/capture/stop");
    return data;
  },

  status: async (): Promise<CaptureStatus> => {
    const { data } = await apiClient.get<CaptureStatus>("/capture/status");
    return data;
  },

  interfaces: async (): Promise<CaptureInterface[]> => {
    const { data } = await apiClient.get<CaptureInterface[]>("/capture/interfaces");
    return data;
  },
};