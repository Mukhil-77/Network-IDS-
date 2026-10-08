import { useQuery } from "@tanstack/react-query";
import { captureService, type CaptureStatus } from "../services/captureService";

export function useCaptureStatus() {
  return useQuery({
    queryKey: ["captureStatus"],
    queryFn: captureService.status,
    // Polled every 5s to keep the Avg Prediction Time card live without
    // hammering the API.
    refetchInterval: 5000,
    // Cache for 30 seconds to avoid refetching on every mount
    staleTime: 30000,
    // Keep in cache for 5 minutes after last subscriber unsubscribes
    gcTime: 300000,
    // Show stale data immediately while fetching in background
    placeholderData: (previousData) => previousData,
  });
}

export type { CaptureStatus };