export interface NotificationTestRequest {
  severity: string;
  message?: string;
}

export interface NotificationTestResult {
  severity: string;
  channels_attempted: string[];
  results: Record<string, { success: boolean; message: string }>;
}

export type NotificationRules = Record<string, string[]>;

export const NOTIFICATION_CHANNELS = ["email", "telegram", "webhook", "dashboard"] as const;

export interface ChannelSettings {
  email: {
    smtp_host: string;
    smtp_port: number;
    smtp_username: string;
    smtp_password: string;
    from_address: string;
    to_address: string;
  };
  telegram: {
    bot_token: string;
    chat_id: string;
  };
  webhook: {
    url: string;
  };
}

export interface NotificationSettingsUpdate {
  email?: Partial<ChannelSettings["email"]>;
  telegram?: Partial<ChannelSettings["telegram"]>;
  webhook?: Partial<ChannelSettings["webhook"]>;
}