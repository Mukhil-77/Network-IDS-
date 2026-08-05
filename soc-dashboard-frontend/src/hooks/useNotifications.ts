import { useMutation } from "@tanstack/react-query";
import { notificationsService } from "../services/notificationsService";
import type { NotificationTestRequest } from "../types/notifications";

export function useTestNotification() {
  return useMutation({
    mutationFn: (payload: NotificationTestRequest) => notificationsService.test(payload),
  });
}
