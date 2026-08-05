import { apiClient } from "./apiClient";
import type { Incident, IncidentCreateRequest, IncidentFilters, IncidentUpdateRequest, PaginatedIncidents } from "../types/incidents";

export const incidentsService = {
  list: async (filters: IncidentFilters): Promise<PaginatedIncidents> => {
    const { data } = await apiClient.get<PaginatedIncidents>("/incidents", { params: filters });
    return data;
  },

  create: async (payload: IncidentCreateRequest): Promise<Incident> => {
    const { data } = await apiClient.post<Incident>("/incidents", payload);
    return data;
  },

  update: async (id: string, payload: IncidentUpdateRequest): Promise<Incident> => {
    const { data } = await apiClient.put<Incident>(`/incidents/${id}`, payload);
    return data;
  },
};
