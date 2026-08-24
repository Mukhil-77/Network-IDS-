import { useMutation, useQuery } from "@tanstack/react-query";
import { reportsService } from "../services/reportsService";
import type { ReportGenerateRequest } from "../types/reports";

export function useReportTypes() {
  return useQuery({ queryKey: ["reports", "types"], queryFn: reportsService.list });
}

export function useGenerateReport() {
  return useMutation({
    mutationFn: (request: ReportGenerateRequest) => reportsService.generate(request),
  });
}
