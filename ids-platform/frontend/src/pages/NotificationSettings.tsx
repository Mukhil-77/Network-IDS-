import { useState } from "react";

import { useTestNotification } from "../hooks/useNotifications";

const SEVERITIES = ["Critical", "High", "Medium", "Low"];

// Mirrors backend/notifications/config/notification_rules.yaml's defaults -
// display only; the backend file is the source of truth. No GET endpoint
// exists yet to fetch the live rules (only POST /notifications/test was
// in this milestone's REST API list) - editing rules today means editing
// that YAML file directly, same as response_rules.yaml before Milestone 8
// added an editing endpoint for it.
const DEFAULT_RULES: Record<string, string[]> = {
  Critical: ["email", "telegram", "webhook"],
  High: ["email"],
  Medium: ["telegram"],
  Low: ["dashboard"],
};

export default function NotificationSettings() {
  const [severity, setSeverity] = useState("Critical");
  const [message, setMessage] = useState("This is a test notification from the SOC platform.");
  const testMutation = useTestNotification();

  return (
    <div className="space-y-6">
      <h1 className="text-lg font-semibold text-slate-100">Notification Settings</h1>

      <div className="rounded-xl border border-border bg-surface-raised p-4">
        <h2 className="mb-3 text-sm font-medium text-slate-300">Configured Rules</h2>
        <p className="mb-3 text-xs text-slate-500">
          Severity → channel mapping, configured via <code className="font-mono">notification_rules.yaml</code>.
        </p>
        <table className="w-full text-left text-sm">
          <thead className="text-xs uppercase tracking-wide text-slate-500">
            <tr><th className="py-2">Severity</th><th className="py-2">Channels</th></tr>
          </thead>
          <tbody className="divide-y divide-border">
            {Object.entries(DEFAULT_RULES).map(([sev, channels]) => (
              <tr key={sev}>
                <td className="py-2 text-slate-200">{sev}</td>
                <td className="py-2 font-mono text-xs text-slate-400">{channels.join(" + ")}</td>
              </tr>
            ))}
          </tbody>
        </table>
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
