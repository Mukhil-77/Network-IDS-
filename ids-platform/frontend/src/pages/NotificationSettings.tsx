import { useEffect, useState } from "react";

import {
  useNotificationRules,
  useNotificationSettings,
  useTestNotification,
  useUpdateNotificationRules,
  useUpdateNotificationSettings,
} from "../hooks/useNotifications";
import { NOTIFICATION_CHANNELS } from "../types/notifications";

const SEVERITIES = ["Critical", "High", "Medium", "Low"];
const CHANNEL_LABELS: Record<string, string> = {
  email: "Email",
  telegram: "Telegram",
  webhook: "Webhook",
  dashboard: "Dashboard",
};

export default function NotificationSettings() {
  const [severity, setSeverity] = useState("Critical");
  const [message, setMessage] = useState("This is a test notification from the SOC platform.");
  const testMutation = useTestNotification();

  const rulesQuery = useNotificationRules();
  const updateRulesMutation = useUpdateNotificationRules();
  const [rulesDraft, setRulesDraft] = useState<Record<string, string[]>>({});

  const settingsQuery = useNotificationSettings();
  const updateSettingsMutation = useUpdateNotificationSettings();
  const [draft, setDraft] = useState<Record<string, Record<string, string>>>({});
  const [rulesError, setRulesError] = useState<string | null>(null);
  const [settingsError, setSettingsError] = useState<string | null>(null);

  // Sync server state into local drafts once it loads.
  useEffect(() => {
    if (rulesQuery.data) setRulesDraft(rulesQuery.data);
  }, [rulesQuery.data]);

  useEffect(() => {
    if (settingsQuery.data) {
      const flat: Record<string, Record<string, string>> = {
        email: { ...settingsQuery.data.email, smtp_port: String(settingsQuery.data.email?.smtp_port ?? 587) },
        telegram: { ...settingsQuery.data.telegram },
        webhook: { ...settingsQuery.data.webhook },
      };
      setDraft(flat);
    }
  }, [settingsQuery.data]);

  const toggleChannel = (sev: string, channel: string) => {
    setRulesDraft((current) => {
      const channels = current[sev] ?? [];
      const next = channels.includes(channel) ? channels.filter((c) => c !== channel) : [...channels, channel];
      return { ...current, [sev]: next };
    });
  };

  const saveRules = async () => {
    setRulesError(null);
    try {
      await updateRulesMutation.mutateAsync(rulesDraft);
    } catch (e) {
      setRulesError((e as Error).message);
    }
  };

  const setField = (channel: string, field: string, value: string) => {
    setDraft((current) => ({ ...current, [channel]: { ...(current[channel] ?? {}), [field]: value } }));
  };

  const saveChannel = async (channel: "email" | "telegram" | "webhook") => {
    setSettingsError(null);
    const values = { ...draft[channel] };
    if (channel === "email") {
      values.smtp_port = values.smtp_port === undefined || values.smtp_port === "" ? "587" : values.smtp_port;
    }
    try {
      await updateSettingsMutation.mutateAsync({ [channel]: values });
    } catch (e) {
      setSettingsError((e as Error).message);
    }
  };

  const savePending = updateRulesMutation.isPending || updateSettingsMutation.isPending;

  const inputClass =
    "w-full rounded-md border border-border bg-surface-raised px-3 py-1.5 text-sm text-slate-100 focus:border-signal focus:outline-none";

  const channelField = (channel: string, field: string, label: string, type = "text", hint?: string) => (
    <div>
      <label className="mb-1 block text-xs text-slate-500">
        {label}
        {hint && <span className="ml-1 text-slate-600">({hint})</span>}
      </label>
      <input
        type={type}
        value={draft[channel]?.[field] ?? ""}
        onChange={(e) => setField(channel, field, e.target.value)}
        className={inputClass}
      />
    </div>
  );

  return (
    <div className="space-y-6">
      <h1 className="text-lg font-semibold text-slate-100">Notification Settings</h1>

      <div className="rounded-xl border border-border bg-surface-raised p-4">
        <h2 className="mb-3 text-sm font-medium text-slate-300">Configured Rules</h2>
        <p className="mb-3 text-xs text-slate-500">
          Severity → channel mapping. Toggle the channels each severity should notify on, then save.
        </p>
        {rulesQuery.isLoading ? (
          <p className="text-sm text-slate-500">Loading rules…</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="py-2">Severity</th>
                  {NOTIFICATION_CHANNELS.map((channel) => (
                    <th key={channel} className="py-2 text-center">{CHANNEL_LABELS[channel]}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {SEVERITIES.map((sev) => (
                  <tr key={sev}>
                    <td className="py-2 text-slate-200">{sev}</td>
                    {NOTIFICATION_CHANNELS.map((channel) => (
                      <td key={channel} className="py-2 text-center">
                        <input
                          type="checkbox"
                          checked={(rulesDraft[sev] ?? []).includes(channel)}
                          onChange={() => toggleChannel(sev, channel)}
                          className="accent-signal"
                        />
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <div className="mt-3 flex items-center gap-3">
          <button
            onClick={saveRules}
            disabled={savePending}
            className="rounded-md bg-signal px-4 py-1.5 text-sm font-medium text-surface hover:bg-signal/90 disabled:opacity-40"
          >
            {updateRulesMutation.isPending ? "Saving…" : "Save Rules"}
          </button>
          {rulesError && <span className="text-xs text-severity-critical">{rulesError}</span>}
          {updateRulesMutation.isSuccess && <span className="text-xs text-severity-benign">Rules saved.</span>}
        </div>
      </div>

      <div className="rounded-xl border border-border bg-surface-raised p-4">
        <h2 className="mb-1 text-sm font-medium text-slate-300">Channel Configuration</h2>
        <p className="mb-4 text-xs text-slate-500">
          Configure delivery credentials. Stored in the runtime settings file; empty fields fall back to environment
          values.
        </p>

        {settingsQuery.isLoading ? (
          <p className="text-sm text-slate-500">Loading settings…</p>
        ) : (
          <div className="space-y-6">
            <div className="rounded-lg border border-border bg-surface-overlay p-3">
              <h3 className="mb-3 text-sm font-medium text-slate-200">Email (SMTP)</h3>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {channelField("email", "smtp_host", "SMTP host", "text", "e.g. smtp.gmail.com")}
                {channelField("email", "smtp_port", "SMTP port", "number")}
                {channelField("email", "smtp_username", "SMTP username")}
                {channelField("email", "smtp_password", "SMTP password", "password")}
                {channelField("email", "from_address", "From address")}
                {channelField("email", "to_address", "Recipient address")}
              </div>
              <button
                onClick={() => saveChannel("email")}
                disabled={savePending}
                className="mt-3 rounded-md border border-border px-3 py-1.5 text-sm font-medium text-slate-300 hover:border-signal/50 hover:text-signal disabled:opacity-40"
              >
                {updateSettingsMutation.isPending ? "Saving…" : "Save Email"}
              </button>
            </div>

            <div className="rounded-lg border border-border bg-surface-overlay p-3">
              <h3 className="mb-3 text-sm font-medium text-slate-200">Telegram</h3>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                {channelField("telegram", "bot_token", "Bot token")}
                {channelField("telegram", "chat_id", "Chat ID")}
              </div>
              <button
                onClick={() => saveChannel("telegram")}
                disabled={savePending}
                className="mt-3 rounded-md border border-border px-3 py-1.5 text-sm font-medium text-slate-300 hover:border-signal/50 hover:text-signal disabled:opacity-40"
              >
                {updateSettingsMutation.isPending ? "Saving…" : "Save Telegram"}
              </button>
            </div>

            <div className="rounded-lg border border-border bg-surface-overlay p-3">
              <h3 className="mb-3 text-sm font-medium text-slate-200">Webhook</h3>
              {channelField("webhook", "url", "Webhook URL", "text", "e.g. https://hooks.slack.com/…")}
              <button
                onClick={() => saveChannel("webhook")}
                disabled={savePending}
                className="mt-3 rounded-md border border-border px-3 py-1.5 text-sm font-medium text-slate-300 hover:border-signal/50 hover:text-signal disabled:opacity-40"
              >
                {updateSettingsMutation.isPending ? "Saving…" : "Save Webhook"}
              </button>
            </div>
          </div>
        )}

        {settingsError && <p className="mt-3 text-xs text-severity-critical">{settingsError}</p>}
        {updateSettingsMutation.isSuccess && (
          <p className="mt-3 text-xs text-severity-benign">Channel settings saved.</p>
        )}
      </div>

      <div className="rounded-xl border border-border bg-surface-raised p-4">
        <h2 className="mb-3 text-sm font-medium text-slate-300">Test a Channel</h2>
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <label className="mb-1 block text-xs text-slate-500">Severity</label>
            <select
              value={severity} onChange={(e) => setSeverity(e.target.value)}
              className="rounded-md border border-border bg-surface-raised px-3 py-1.5 text-sm text-slate-100 focus:border-signal focus:outline-none"
            >
              {SEVERITIES.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
          <div className="min-w-[280px] flex-1">
            <label className="mb-1 block text-xs text-slate-500">Message</label>
            <input
              value={message} onChange={(e) => setMessage(e.target.value)}
              className="w-full rounded-md border border-border bg-surface-raised px-3 py-1.5 text-sm text-slate-100 focus:border-signal focus:outline-none"
            />
          </div>
          <button
            onClick={() => testMutation.mutate({ severity, message })} disabled={testMutation.isPending}
            className="rounded-md bg-signal px-4 py-1.5 text-sm font-medium text-surface hover:bg-signal/90 disabled:opacity-40"
          >
            {testMutation.isPending ? "Sending…" : "Send Test"}
          </button>
        </div>

        {testMutation.data && (
          <div className="mt-4 space-y-2 rounded-lg border border-border bg-surface-overlay p-3">
            {Object.entries(testMutation.data.results).map(([channel, result]) => (
              <div key={channel} className="flex items-center gap-2 text-sm">
                <span className={`h-2 w-2 rounded-full ${result.success ? "bg-severity-benign" : "bg-severity-critical"}`} />
                <span className="font-mono text-slate-200">{channel}</span>
                <span className="text-xs text-slate-500">{result.message}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}