export interface NotificationTestRequest {
  severity: string;
  message?: string;
}

export interface NotificationTestResult {
  severity: string;
  channels_attempted: string[];
  results: Record<string, { success: boolean; message: string }>;
}
