import { useEffect, useState } from "react";

import { useResponseRules, useUpdateResponseRules } from "../hooks/useResponses";
import { CardSkeleton } from "../components/common/LoadingSkeleton";
import { ErrorState } from "../components/common/ErrorState";

const SEVERITIES = ["Critical", "High", "Medium", "Low"] as const;

const SEVERITY_STYLE: Record<string, string> = {
  Critical: "bg-severity-critical/10 text-severity-critical border-severity-critical/30",
  High: "bg-severity-high/10 text-severity-high border-severity-high/30",
  Medium: "bg-severity-medium/10 text-severity-medium border-severity-medium/30",
  Low: "bg-severity-low/10 text-severity-low border-severity-low/30",
};

/**
 * Policy Manager: edit severity -> action mappings and the global
 * simulation-mode flag (PUT /response-rules, which persists to
 * backend/response_engine/config/response_rules.yaml).
 */
export default function PolicyManager() {
  const rulesQuery = useResponseRules();
  const updateMutation = useUpdateResponseRules();

  const [policies, setPolicies] = useState<Record<string, string[]>>({});
  const [simulationMode, setSimulationMode] = useState(true);

  useEffect(() => {
    if (rulesQuery.data) {
      setPolicies(rulesQuery.data.policies);
      setSimulationMode(rulesQuery.data.simulation_mode);
    }
  }, [rulesQuery.data]);

  const toggleAction = (severity: string, action: string) => {
    setPolicies((current) => {
      const existing = current[severity] ?? [];
      const next = existing.includes(action) ? existing.filter((a) => a !== action) : [...existing, action];
      return { ...current, [severity]: next };
    });
  };

  const handleSave = () => {
    updateMutation.mutate({ policies, simulation_mode: simulationMode });
  };

  if (rulesQuery.isLoading) return <CardSkeleton />;
  if (rulesQuery.isError) return <ErrorState message="Couldn't load response rules." onRetry={() => rulesQuery.refetch()} />;
  if (!rulesQuery.data) return null;

  const { available_actions } = rulesQuery.data;
  const hasUnsavedChanges =
    JSON.stringify(policies) !== JSON.stringify(rulesQuery.data.policies) || simulationMode !== rulesQuery.data.simulation_mode;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-slate-100">Policy Manager</h1>
        <button
          onClick={handleSave}
          disabled={!hasUnsavedChanges || updateMutation.isPending}
          className="rounded-md bg-signal px-4 py-1.5 text-sm font-medium text-surface hover:bg-signal/90 disabled:opacity-40"
        >
          {updateMutation.isPending ? "Saving…" : "Save Changes"}
        </button>
      </div>

      <div className="rounded-xl border border-border bg-surface-raised p-4">
        <h2 className="mb-3 text-sm font-medium text-slate-300">Automatic Responses</h2>
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-slate-200">Simulation Mode</p>
            <p className="text-xs text-slate-500">
              When off, actions run "live" if the backend's <code className="font-mono">ENABLE_LIVE_RESPONSE_ACTIONS</code>{" "}
              setting also allows it (a server-side, operator-only safety gate — this toggle alone cannot enable
              live actions).
            </p>
          </div>
          <button
            onClick={() => setSimulationMode((v) => !v)}
            className={`rounded-md border px-3 py-1.5 text-sm font-medium ${
              simulationMode
                ? "border-signal/30 bg-signal/10 text-signal"
                : "border-severity-high/30 bg-severity-high/10 text-severity-high"
            }`}
          >
            {simulationMode ? "Simulation" : "Live"}
          </button>
        </div>
      </div>

      <div className="rounded-xl border border-border bg-surface-raised overflow-hidden">
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <h2 className="text-sm font-medium text-slate-300">Severity → Action Mappings</h2>
          <span className="text-xs text-slate-500">Check the actions to fire for each severity</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-xs uppercase tracking-wide text-slate-500">
              <tr className="border-b border-border">
                <th className="px-4 py-2.5 text-left font-medium">Severity</th>
                {available_actions.map((action) => (
                  <th key={action} className="px-3 py-2.5 text-center font-mono text-[11px] font-medium">
                    {action}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {SEVERITIES.map((severity) => (
                <tr key={severity} className="hover:bg-surface-overlay/40">
                  <td className="px-4 py-2">
                    <span
                      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium ${SEVERITY_STYLE[severity]}`}
                    >
                      <span className="h-1.5 w-1.5 rounded-full bg-current" />
                      {severity}
                    </span>
                  </td>
                  {available_actions.map((action) => {
                    const enabled = (policies[severity] ?? []).includes(action);
                    return (
                      <td key={action} className="px-3 py-2 text-center">
                        <button
                          type="button"
                          onClick={() => toggleAction(severity, action)}
                          role="checkbox"
                          aria-checked={enabled}
                          aria-label={`${action} for ${severity}`}
                          className={`inline-flex h-6 w-6 items-center justify-center rounded-md border transition-colors ${
                            enabled
                              ? "border-signal/50 bg-signal/15 text-signal"
                              : "border-border text-transparent hover:border-slate-500 hover:text-slate-500"
                          }`}
                        >
                          ✓
                        </button>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {updateMutation.isError && <ErrorState message="Failed to save policy changes." />}
      {updateMutation.isSuccess && !hasUnsavedChanges && (
        <p className="text-xs text-severity-benign">Policies saved.</p>
      )}
    </div>
  );
}
