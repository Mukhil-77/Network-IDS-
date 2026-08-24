import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { responsesService } from "../services/responsesService";
import type { ResponseExecuteRequest, ResponseFilters, ResponseRulesConfig } from "../types/response";

export function useResponses(filters: ResponseFilters) {
  return useQuery({
    queryKey: ["responses", filters],
    queryFn: () => responsesService.list(filters),
    placeholderData: (previous) => previous,
  });
}

export function useResponseHistory(limit = 20) {
  return useQuery({
    queryKey: ["responses", "history", limit],
    queryFn: () => responsesService.history(limit),
  });
}

export function useResponseRules() {
  return useQuery({
    queryKey: ["response-rules"],
    queryFn: responsesService.getRules,
  });
}

export function useExecuteResponse() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (request: ResponseExecuteRequest) => responsesService.execute(request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["responses"] });
      queryClient.invalidateQueries({ queryKey: ["alerts"] }); // alert.status changes too
    },
  });
}

export function useRollbackResponse() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (responseId: string) => responsesService.rollback(responseId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["responses"] }),
  });
}

export function useUpdateResponseRules() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (update: Partial<ResponseRulesConfig>) => responsesService.updateRules(update),
    onSuccess: (data) => queryClient.setQueryData(["response-rules"], data),
  });
}
