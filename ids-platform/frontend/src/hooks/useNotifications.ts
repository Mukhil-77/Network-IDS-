import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { notificationsService } from "../services/notificationsService";
import type {
  ChannelSettings,
  NotificationRules,
  NotificationSettingsUpdate,
  NotificationTestRequest,
} from "../types/notifications";

export function useTestNotification() {
  return useMutation({
    mutationFn: (payload: NotificationTestRequest) => notificationsService.test(payload),
  });
}

export function useNotificationRules() {
  return useQuery({
    queryKey: ["notifications", "rules"],
    queryFn: notificationsService.getRules,
    placeholderData: (previous) => previous,
  });
}

export function useUpdateNotificationRules() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (rules: NotificationRules) => notificationsService.updateRules(rules),
    onSuccess: (data) => {
      queryClient.setQueryData(["notifications", "rules"], data);
    },
  });
}

export function useNotificationSettings() {
  return useQuery({
    queryKey: ["notifications", "settings"],
    queryFn: notificationsService.getSettings,
    placeholderData: (previous) => previous,
  });
}

export function useUpdateNotificationSettings() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (update: NotificationSettingsUpdate) => notificationsService.updateSettings(update),
    onSuccess: (data: ChannelSettings) => {
      queryClient.setQueryData(["notifications", "settings"], data);
    },
  });
}