import { useQuery } from "@tanstack/react-query";
import { modelService } from "../services/modelService";

export function useModelInfo() {
  return useQuery({
    queryKey: ["model", "info"],
    queryFn: modelService.getInfo,
    staleTime: 5 * 60_000, // model metadata changes only on retrain - no need to refetch aggressively
  });
}
