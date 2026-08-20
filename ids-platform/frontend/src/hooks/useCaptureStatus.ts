import { useQuery } from "@tanstack/react-query";
import { captureService, type CaptureStatus } from "../services/captureService";

export function useCaptureStatus() {
  return useQuery({
    queryKey: ["captureStatus"],
    queryFn: captureService.status,
    // Polled every 5s in CaptureControl already; on the Dashboard we poll a
    // bit less often to keep the Avg Prediction Time card live without
    // hammering the API.
    refetchInterval: 5000,
    placeholderData: (previous) => previous,
  });
}

export type { CaptureStatus };