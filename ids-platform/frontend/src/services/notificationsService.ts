import { apiClient } from "./apiClient";
import type {
  ChannelSettings,
  NotificationRules,
  NotificationSettingsUpdate,
  NotificationTestRequest,
  NotificationTestResult,
} from "../types/notifications";

export const notificationsService = {
  test: async (payload: NotificationTestRequest): Promise<NotificationTestResult> => {
    const { data } = await apiClient.post<NotificationTestResult>("/notifications/test", payload);
    return data;
  },

  getRules: async (): Promise<NotificationRules> => {
    const { data } = await apiClient.get<NotificationRules>("/notifications/rules");
    return data;
  },

  updateRules: async (rules: NotificationRules): Promise<NotificationRules> => {
    const { data } = await apiClient.put<NotificationRules>("/notifications/rules", { rules });
    return data;
  },

  getSettings: async (): Promise<ChannelSettings> => {
    const { data } = await apiClient.get<ChannelSettings>("/notifications/settings");
    return data;
  },

  updateSettings: async (update: NotificationSettingsUpdate): Promise<ChannelSettings> => {
    const { data } = await apiClient.put<ChannelSettings>("/notifications/settings", update);
    return data;
  },
};