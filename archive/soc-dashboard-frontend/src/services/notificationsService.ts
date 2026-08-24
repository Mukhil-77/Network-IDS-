import { apiClient } from "./apiClient";
import type { NotificationTestRequest, NotificationTestResult } from "../types/notifications";

export const notificationsService = {
  test: async (payload: NotificationTestRequest): Promise<NotificationTestResult> => {
    const { data } = await apiClient.post<NotificationTestResult>("/notifications/test", payload);
    return data;
  },
};
