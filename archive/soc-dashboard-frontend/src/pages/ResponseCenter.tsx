import { useState } from "react";

import { useLatestAlerts } from "../hooks/useAlerts";
import { useExecuteResponse, useResponseHistory, useResponseRules, useRollbackResponse } from "../hooks/useResponses";
import { ResponseHistoryTable } from "../components/responses/ResponseHistoryTable";
import { SeverityBadge } from "../components/common/Badge";
import { TableSkeleton } from "../components/common/LoadingSkeleton";
import { ErrorState } from "../components/common/ErrorState";

/**
 * Response Center: trigger a response manually for a recent alert (the
 * "analyst override" path - POST /responses/execute), and watch the live
 * feed of what's happened (auto-triggered responses land here too, since
 * every alert runs through response_service.handle_alert automatically -
 * see backend/main.py's lifespan wiring).
 */
export default function ResponseCenter() {
  const [selectedAlertId, setSelectedAlertId] = useState<string>("");
  const [actionsOverride, setActionsOverride] = useState<string>("");

  const alertsQuery = useLatestAlerts(20);
  const rulesQuery = useResponseRules();
  const historyQuery = useResponseHistory(20);
  const executeMutation = useExecuteResponse();
  const rollbackMutation = useRollbackResponse();

  const handleExecute = () => {
    if (!selectedAlertId) return;
    const actions = actionsOverride.trim() ? actionsOverride.split(",").map((a) => a.trim()) : undefined;
    executeMutation.mutate({ alert_id: selectedAlertId, actions });
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-slate-100">Response Center</h1>
        {rulesQuery.data && (
          <span
            className={`inline-flex items-center rounded-md border px-2.5 py-1 text-xs font-medium ${
              rulesQuery.data.simulation_mode
                ? "border-signal/30 bg-signal/10 text-signal"
                : "border-severity-high/30 bg-severity-high/10 text-severity-high"
            }`}
          >
            {rulesQuery.data.simulation_mode ? "Simulation Mode" : "LIVE MODE"}
          </span>
        )}
      </div>

      <div className="rounded-xl border border-border bg-surface-raised p-4">
        <h2 className="mb-3 text-sm font-medium text-slate-300">Trigger a Response</h2>
        <p className="mb-3 text-xs text-slate-500">
          Every alert already triggers its severity's policy automatically. Use this to re-run a response, or
          override with a specific action list (comma-separated action names).
        </p>
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex-1 min-w-[240px]">
            <label className="mb-1 block text-xs text-slate-500">Alert</label>
            <select
              value={selectedAlertId}
              onChange={(e) => setSelectedAlertId(e.target.value)}
              className="w-full rounded-md border border-border bg-surface-raised px-3 py-1.5 text-sm text-slate-100 focus:border-signal focus:outline-none"
            >
              <option value="">Select a recent alert…</option>
              {alertsQuery.data?.map((alert) => (
                <option key={alert.id} value={alert.id}>
                  {alert.attack_type} ({alert.severity}) — {alert.source_ip} → {alert.destination_ip}
                </option>
              ))}
            </select>
          </div>
          <div className="flex-1 min-w-[240px]">
            <label className="mb-1 block text-xs text-slate-500">Actions override (optional)</label>
            <input
              type="text"
              value={actionsOverride}
              onChange={(e) => setActionsOverride(e.target.value)}
              placeholder="e.g. block_ip, log_response"
              className="w-full rounded-md border border-border bg-surface-raised px-3 py-1.5 text-sm text-slate-100 placeholder:text-slate-500 focus:border-signal focus:outline-none"
            />
          </div>
          <button
            onClick={handleExecute}
            disabled={!selectedAlertId || executeMutation.isPending}
            className="rounded-md bg-signal px-4 py-1.5 text-sm font-medium text-surface hover:bg-signal/90 disabled:opacity-40"
          >
            {executeMutation.isPending ? "Executing…" : "Execute Response"}
          </button>
        </div>

        {executeMutation.isSuccess && (
          <div className="mt-4 space-y-2 rounded-lg border border-border bg-surface-overlay p-3">
            <p className="text-xs font-medium text-slate-400">Result:</p>
            {executeMutation.data.map((r) => (
              <div key={r.id} className="flex items-center gap-2 text-sm">
                <SeverityBadge severity={r.status === "success" ? "Low" : "Critical"} />
                <span className="text-slate-200">{r.action}</span>
                <span className="text-xs text-slate-500">{r.message}</span>
              </div>
            ))}
          </div>
        )}
        {executeMutation.isError && <ErrorState message="Failed to execute response." />}
      </div>

      <div>
        <h2 className="mb-3 text-sm font-medium text-slate-300">Recent Response Activity</h2>
        {historyQuery.isLoading && <TableSkeleton />}
        {historyQuery.isError && <ErrorState message="Couldn't load response history." onRetry={() => historyQuery.refetch()} />}
        {historyQuery.data && (
          <ResponseHistoryTable
            responses={historyQuery.data}
            onRollback={(id) => rollbackMutation.mutate(id)}
            rollingBackId={rollbackMutation.isPending ? rollbackMutation.variables : undefined}
          />
        )}
      </div>
    </div>
  );
}
