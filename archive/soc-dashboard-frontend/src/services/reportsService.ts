import { apiClient } from "./apiClient";
import type { ReportGenerateRequest, ReportSummary } from "../types/reports";

export const reportsService = {
  list: async (): Promise<ReportSummary[]> => {
    const { data } = await apiClient.get<ReportSummary[]>("/reports");
    return data;
  },

  generate: async (request: ReportGenerateRequest): Promise<Blob> => {
    const { data } = await apiClient.post("/reports/generate", request, { responseType: "blob" });
    return data;
  },
};
