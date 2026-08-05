import { useQuery } from "@tanstack/react-query";
import { threatIntelService } from "../services/threatIntelService";

export function useThreatIndicators(tag?: string) {
  return useQuery({
    queryKey: ["threat-intelligence", tag],
    queryFn: () => threatIntelService.list(tag),
  });
}
