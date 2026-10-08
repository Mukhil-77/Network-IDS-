import { useQuery } from "@tanstack/react-query";
import { threatIntelService } from "../services/threatIntelService";

export function useThreatIndicators(tag?: string) {
  return useQuery({
    queryKey: ["threat-intelligence", tag],
    queryFn: () => threatIntelService.list(tag),
    staleTime: 30000,
    gcTime: 300000,
    placeholderData: (previousData) => previousData,
  });
}