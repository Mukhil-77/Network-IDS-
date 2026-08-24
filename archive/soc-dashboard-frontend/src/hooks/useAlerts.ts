import { useQuery } from "@tanstack/react-query";
import { alertsService } from "../services/alertsService";
import type { AlertFilters } from "../types/alert";

export function useAlerts(filters: AlertFilters) {
  return useQuery({
    queryKey: ["alerts", filters],
    queryFn: () => alertsService.list(filters),
    placeholderData: (previous) => previous, // keeps the table visible (not a blank flash) while a new page/filter loads
  });
}

export function useLatestAlerts(limit = 20) {
  return useQuery({
    queryKey: ["alerts", "latest", limit],
    queryFn: () => alertsService.latest(limit),
  });
}

export function useAlert(id: string | undefined) {
  return useQuery({
    queryKey: ["alerts", "detail", id],
    queryFn: () => alertsService.getById(id as string),
    enabled: Boolean(id),
  });
}
