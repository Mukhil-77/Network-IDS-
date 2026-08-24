import { useEffect, useState } from "react";

import { useResponseRules, useUpdateResponseRules } from "../hooks/useResponses";
import { CardSkeleton } from "../components/common/LoadingSkeleton";
import { ErrorState } from "../components/common/ErrorState";

const SEVERITIES = ["Critical", "High", "Medium", "Low"];

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

      <div className="space-y-4">
        <h2 className="text-sm font-medium text-slate-300">Severity → Action Mappings</h2>
        {SEVERITIES.map((severity) => (
          <div key={severity} className="rounded-xl border border-border bg-surface-raised p-4">
            <h3 className="mb-3 text-sm font-semibold text-slate-100">{severity}</h3>
            <div className="flex flex-wrap gap-2">
              {available_actions.map((action) => {
                const enabled = (policies[severity] ?? []).includes(action);
                return (
                  <button
                    key={action}
                    onClick={() => toggleAction(severity, action)}
                    className={`rounded-md border px-2.5 py-1 text-xs font-mono transition-colors ${
                      enabled
                        ? "border-signal/40 bg-signal/10 text-signal"
                        : "border-border text-slate-500 hover:border-slate-500 hover:text-slate-300"
                    }`}
                  >
                    {action}
                  </button>
                );
              })}
            </div>
          </div>
        ))}
      </div>

      {updateMutation.isError && <ErrorState message="Failed to save policy changes." />}
      {updateMutation.isSuccess && !hasUnsavedChanges && (
        <p className="text-xs text-severity-benign">Policies saved.</p>
      )}
    </div>
  );
}
