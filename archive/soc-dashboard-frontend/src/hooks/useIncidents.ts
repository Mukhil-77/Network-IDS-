import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { incidentsService } from "../services/incidentsService";
import type { IncidentCreateRequest, IncidentFilters, IncidentUpdateRequest } from "../types/incidents";

export function useIncidents(filters: IncidentFilters) {
  return useQuery({
    queryKey: ["incidents", filters],
    queryFn: () => incidentsService.list(filters),
    placeholderData: (previous) => previous,
  });
}

export function useCreateIncident() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: IncidentCreateRequest) => incidentsService.create(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["incidents"] }),
  });
}

export function useUpdateIncident() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: IncidentUpdateRequest }) => incidentsService.update(id, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["incidents"] }),
  });
}
