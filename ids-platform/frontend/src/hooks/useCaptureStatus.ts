import { useQuery } from "@tanstack/react-query";
import { captureService, type CaptureStatus } from "../services/captureService";

export function useCaptureStatus() {
  return useQuery({
    queryKey: ["captureStatus"],
    queryFn: captureService.status,
    // Polled every 5s to keep the Avg Prediction Time card live without
    // hammering the API.
    refetchInterval: 5000,
    // Don't show stale data while fetching - show loading state instead
    placeholderData: undefined,
  });
}

export type { CaptureStatus };