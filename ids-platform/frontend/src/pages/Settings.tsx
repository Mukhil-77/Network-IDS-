import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTheme } from "../context/ThemeContext";
import { adminService, CLEAR_SCOPE_LABELS } from "../services/adminService";

export default function Settings() {
  const { theme, toggleTheme } = useTheme();
  const queryClient = useQueryClient();

  const [confirmClear, setConfirmClear] = useState(false);
  const [selectedScopes, setSelectedScopes] = useState<string[]>([]);
  const [clearResult, setClearResult] = useState<Record<string, number> | null>(null);

  const [confirmReset, setConfirmReset] = useState(false);
  const [resetResult, setResetResult] = useState<string[] | null>(null);

  const clearMutation = useMutation({
    mutationFn: adminService.clearData,
    onSuccess: (result) => {
      setClearResult(result.deleted);
      setConfirmClear(false);
      setClearError(null);
      // Stats/analytics/incidents caches are now stale.
      queryClient.invalidateQueries();
    },
  });
  const [clearError, setClearError] = useState<string | null>(null);

  const resetMutation = useMutation({
    mutationFn: adminService.resetModels,
    onSuccess: (result) => {
      setResetResult(result.removed_versions);
      setConfirmReset(false);
      setResetError(null);
      queryClient.invalidateQueries();
    },
  });
  const [resetError, setResetError] = useState<string | null>(null);

  const toggleScope = (key: string) => {
    setSelectedScopes((current) =>
      current.includes(key) ? current.filter((scope) => scope !== key) : [...current, key],
    );
  };

  return (
    <div className="space-y-6">
      <h1 className="text-lg font-semibold text-slate-100">Settings</h1>

      <div className="max-w-xl rounded-xl border border-border bg-surface-raised p-4">
        <h2 className="mb-3 text-sm font-medium text-slate-300">Appearance</h2>
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-slate-200">Dark mode</p>
            <p className="text-xs text-slate-500">Applies across the whole dashboard, saved to this browser.</p>
          </div>
          <button
            onClick={toggleTheme}
            className="rounded-md border border-border bg-surface-overlay px-3 py-1.5 text-sm font-medium text-slate-100 hover:border-signal/50 hover:text-signal"
          >
            {theme === "dark" ? "Switch to light" : "Switch to dark"}
          </button>
        </div>
      </div>

      <div className="max-w-xl rounded-xl border border-border bg-surface-raised p-4">
        <h2 className="mb-3 text-sm font-medium text-slate-300">Connection</h2>
        <dl className="grid grid-cols-2 gap-y-2 text-sm">
          <dt className="text-slate-500">API base URL</dt>
          <dd className="font-mono text-slate-300">{import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000"}</dd>
          <dt className="text-slate-500">WebSocket URL</dt>
          <dd className="font-mono text-slate-300">{import.meta.env.VITE_WS_URL ?? "ws://localhost:8000/ws/alerts"}</dd>
        </dl>
        <p className="mt-3 text-xs text-slate-500">
          Set via <code className="font-mono">VITE_API_BASE_URL</code> / <code className="font-mono">VITE_WS_URL</code> in
          <code className="font-mono"> .env</code> - see <code className="font-mono">.env.example</code>.
        </p>
      </div>

      <div className="max-w-xl rounded-xl border border-red-500/30 bg-red-500/[0.04] p-4">
        <h2 className="mb-1 text-sm font-medium text-red-400">Danger Zone</h2>
        <p className="mb-4 text-xs text-slate-500">
          Destructive, permanent actions. Both require the <code className="font-mono">settings:write</code> permission.
        </p>

        <div className="space-y-4">
          <div className="rounded-lg border border-border bg-surface-overlay p-3">
            <div className="flex items-center justify-between gap-4">
              <div>
                <h3 className="text-sm font-medium text-slate-200">Delete data</h3>
                <p className="mt-0.5 text-xs text-slate-500">
                  Delete alerts, flows, responses, incidents, statistics, logs… across selected scopes.
                </p>
              </div>
              <button
                onClick={() => {
                  setConfirmClear(true);
                  setClearError(null);
                  setClearResult(null);
                }}
                className="shrink-0 rounded-md border border-red-500/40 px-3 py-1.5 text-sm font-medium text-red-400 hover:bg-red-500/10"
              >
                Delete data…
              </button>
            </div>

            {confirmClear && (
              <div className="mt-4 border-t border-border pt-3">
                <p className="mb-2 text-xs text-slate-400">Choose scopes to delete (none selected = delete everything):</p>
                <div className="grid grid-cols-1 gap-1 sm:grid-cols-2">
                  {CLEAR_SCOPE_LABELS.map(({ key, label }) => (
                    <label key={key} className="flex cursor-pointer items-center gap-2 text-sm text-slate-300">
                      <input
                        type="checkbox"
                        checked={selectedScopes.includes(key)}
                        onChange={() => toggleScope(key)}
                        className="accent-red-500"
                      />
                      {label}
                    </label>
                  ))}
                </div>
                <div className="mt-3 flex items-center justify-end gap-2">
                  <button
                    onClick={() => setConfirmClear(false)}
                    className="rounded-md border border-border px-3 py-1.5 text-sm font-medium text-slate-300 hover:bg-surface-overlay"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={() => clearMutation.mutate(selectedScopes)}
                    disabled={clearMutation.isPending}
                    className="rounded-md bg-red-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-red-500 disabled:opacity-50"
                  >
                    {clearMutation.isPending ? "Deleting…" : "Confirm delete"}
                  </button>
                </div>
              </div>
            )}

            {clearError && <p className="mt-2 text-xs text-red-400">{clearError}</p>}
            {clearResult && (
              <div className="mt-3 rounded border border-emerald-500/30 bg-emerald-500/10 p-2 text-xs text-emerald-300">
                Deleted {Object.values(clearResult).reduce((sum, count) => sum + count, 0)} rows:
                <ul className="mt-1 list-inside list-disc">
                  {Object.entries(clearResult).map(([scope, count]) => (
                    <li key={scope}>
                      {scope}: {count}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          <div className="rounded-lg border border-border bg-surface-overlay p-3">
            <div className="flex items-center justify-between gap-4">
              <div>
                <h3 className="text-sm font-medium text-slate-200">Reset models</h3>
                <p className="mt-0.5 text-xs text-slate-500">
                  Delete every trained model version from disk and its DB metadata. Detection stops until a new model
                  is deployed.
                </p>
              </div>
              <button
                onClick={() => {
                  setConfirmReset(true);
                  setResetError(null);
                  setResetResult(null);
                }}
                className="shrink-0 rounded-md border border-red-500/40 px-3 py-1.5 text-sm font-medium text-red-400 hover:bg-red-500/10"
              >
                Reset models…
              </button>
            </div>

            {confirmReset && (
              <div className="mt-4 border-t border-border pt-3">
                <p className="mb-3 text-xs text-slate-400">
                  This deletes <strong className="text-slate-200">all</strong> model versions and unloads the active
                  predictor. Are you sure?
                </p>
                <div className="flex items-center justify-end gap-2">
                  <button
                    onClick={() => setConfirmReset(false)}
                    className="rounded-md border border-border px-3 py-1.5 text-sm font-medium text-slate-300 hover:bg-surface-overlay"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={() => resetMutation.mutate()}
                    disabled={resetMutation.isPending}
                    className="rounded-md bg-red-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-red-500 disabled:opacity-50"
                  >
                    {resetMutation.isPending ? "Resetting…" : "Confirm reset"}
                  </button>
                </div>
              </div>
            )}

            {resetError && <p className="mt-2 text-xs text-red-400">{resetError}</p>}
            {resetResult && (
              <div className="mt-3 rounded border border-emerald-500/30 bg-emerald-500/10 p-2 text-xs text-emerald-300">
                Removed versions: {resetResult.join(", ") || "(none)"}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}