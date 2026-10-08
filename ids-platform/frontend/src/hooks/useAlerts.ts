import { useQuery } from "@tanstack/react-query";
import { alertsService } from "../services/alertsService";
import type { AlertFilters } from "../types/alert";

export function useAlerts(filters: AlertFilters) {
  return useQuery({
    queryKey: ["alerts", filters],
    queryFn: () => alertsService.list(filters),
    placeholderData: (previous) => previous,
    staleTime: 30000,
    gcTime: 300000,
  });
}

export function useLatestAlerts(limit = 20) {
  return useQuery({
    queryKey: ["alerts", "latest", limit],
    queryFn: () => alertsService.latest(limit),
    staleTime: 30000,
    gcTime: 300000,
    placeholderData: (previousData) => previousData,
  });
}

export function useAlert(id: string | undefined) {
  return useQuery({
    queryKey: ["alerts", "detail", id],
    queryFn: () => alertsService.getById(id as string),
    enabled: Boolean(id),
    staleTime: 30000,
    gcTime: 300000,
    placeholderData: (previousData) => previousData,
  });
}