import { useQuery } from "@tanstack/react-query";
import { apiClient } from "../services/apiClient";

interface ExperimentResult {
  experiment_id: string;
  name: string;
  description: string;
  status: "completed" | "running" | "failed" | "pending";
  started_at: string;
  completed_at?: string;
  metrics: Record<string, number>;
  parameters: Record<string, any>;
  baseline_metrics?: Record<string, number>;
  improvement?: Record<string, number>;
}

interface ExperimentSummary {
  total: number;
  completed: number;
  running: number;
  failed: number;
  pending: number;
}

function getStatusBadgeClass(status: string): string {
  switch (status) {
    case "completed":
      return "bg-emerald-100 text-emerald-800 border-emerald-300";

    case "running":
      return "bg-blue-100 text-blue-800 border-blue-300";

    case "pending":
      return "bg-slate-100 text-slate-800 border-slate-300";

    case "failed":
      return "bg-red-100 text-red-800 border-red-300";

    default:
      return "bg-slate-100 text-slate-800 border-slate-300";
  }
}

function formatDuration(started: string, completed: string): string {
  const start = new Date(started);
  const end = new Date(completed);

  const diffMs = end.getTime() - start.getTime();

  if (diffMs < 0 || Number.isNaN(diffMs)) {
    return "—";
  }

  const minutes = Math.floor(diffMs / 60000);
  const hours = Math.floor(minutes / 60);

  if (hours > 0) {
    return `${hours}h ${minutes % 60}m`;
  }

  return `${minutes}m`;
}

export default function ExperimentDashboard() {
  const experimentsQuery = useQuery({
    queryKey: ["experiments"],
    queryFn: async () => {
      const { data } =
        await apiClient.get<ExperimentResult[]>("/experiments");

      return data;
    },
    refetchInterval: 30_000,
  });

  const summaryQuery = useQuery({
    queryKey: ["experiments", "summary"],
    queryFn: async () => {
      const { data } =
        await apiClient.get<ExperimentSummary>("/experiments/summary");

      return data;
    },
    refetchInterval: 30_000,
  });

  /*
   * Loading state
   */
  if (experimentsQuery.isLoading || summaryQuery.isLoading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="h-8 bg-slate-700 rounded w-1/4" />

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-5">
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="h-20 bg-slate-700 rounded" />
          ))}
        </div>

        <div className="h-96 bg-slate-700 rounded" />
      </div>
    );
  }

  /*
   * Error state
   */
  if (experimentsQuery.isError || summaryQuery.isError) {
    return (
      <div className="rounded-xl border border-border bg-surface-raised p-4 text-center text-slate-500">
        Failed to load experiments.
      </div>
    );
  }

  const experiments = experimentsQuery.data ?? [];
  const summary = summaryQuery.data;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-slate-100">
          Research Experiments
        </h1>

        <button
          type="button"
          className="rounded-md bg-signal px-4 py-2 text-sm font-medium text-slate-100 hover:bg-signal/80"
        >
          New Experiment
        </button>
      </div>

      {/* Summary */}
      {summary && (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-5">
          <div className="bg-surface p-3 rounded-lg">
            <dt className="text-xs text-slate-500">Total</dt>
            <dd className="font-mono text-2xl text-slate-100">
              {summary.total}
            </dd>
          </div>

          <div className="bg-surface p-3 rounded-lg">
            <dt className="text-xs text-slate-500">Completed</dt>
            <dd className="font-mono text-2xl text-emerald-400">
              {summary.completed}
            </dd>
          </div>

          <div className="bg-surface p-3 rounded-lg">
            <dt className="text-xs text-slate-500">Running</dt>
            <dd className="font-mono text-2xl text-blue-400">
              {summary.running}
            </dd>
          </div>

          <div className="bg-surface p-3 rounded-lg">
            <dt className="text-xs text-slate-500">Failed</dt>
            <dd className="font-mono text-2xl text-red-400">
              {summary.failed}
            </dd>
          </div>

          <div className="bg-surface p-3 rounded-lg">
            <dt className="text-xs text-slate-500">Pending</dt>
            <dd className="font-mono text-2xl text-slate-400">
              {summary.pending}
            </dd>
          </div>
        </div>
      )}

      {/* Experiments table */}
      <div className="rounded-xl border border-border bg-surface-raised">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-border bg-surface-raised text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3 font-medium">Experiment</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Type</th>
                <th className="px-4 py-3 font-medium">Accuracy</th>
                <th className="px-4 py-3 font-medium">F1-Macro</th>
                <th className="px-4 py-3 font-medium">FPR</th>
                <th className="px-4 py-3 font-medium">FNR</th>
                <th className="px-4 py-3 font-medium">MCC</th>
                <th className="px-4 py-3 font-medium">Improvement</th>
                <th className="px-4 py-3 font-medium">Duration</th>
              </tr>
            </thead>

            <tbody className="divide-y divide-border">
              {experiments.map((exp) => (
                <tr
                  key={exp.experiment_id}
                  className="hover:bg-surface-raised/60"
                >
                  {/* Experiment */}
                  <td className="px-4 py-3 font-medium text-slate-100">
                    {exp.name}
                  </td>

                  {/* Status */}
                  <td className="px-4 py-3">
                    <span
                      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${getStatusBadgeClass(
                        exp.status
                      )}`}
                    >
                      {exp.status}
                    </span>
                  </td>

                  {/* Type */}
                  <td className="px-4 py-3 text-slate-300">
                    {exp.parameters?.experiment_type || "—"}
                  </td>

                  {/* Accuracy */}
                  <td className="px-4 py-3 font-mono text-slate-300">
                    {exp.metrics?.accuracy !== undefined
                      ? `${(exp.metrics.accuracy * 100).toFixed(1)}%`
                      : "—"}
                  </td>

                  {/* F1 Macro */}
                  <td className="px-4 py-3 font-mono text-slate-300">
                    {exp.metrics?.f1_macro !== undefined
                      ? `${(exp.metrics.f1_macro * 100).toFixed(1)}%`
                      : "—"}
                  </td>

                  {/* FPR */}
                  <td className="px-4 py-3 font-mono text-slate-300">
                    {exp.metrics?.fpr !== undefined
                      ? `${(exp.metrics.fpr * 100).toFixed(2)}%`
                      : "—"}
                  </td>

                  {/* FNR */}
                  <td className="px-4 py-3 font-mono text-slate-300">
                    {exp.metrics?.fnr !== undefined
                      ? `${(exp.metrics.fnr * 100).toFixed(2)}%`
                      : "—"}
                  </td>

                  {/* MCC */}
                  <td className="px-4 py-3 font-mono text-slate-300">
                    {exp.metrics?.mcc !== undefined
                      ? exp.metrics.mcc.toFixed(3)
                      : "—"}
                  </td>

                  {/* Improvement */}
                  <td className="px-4 py-3 font-mono text-slate-300">
                    {exp.improvement?.f1_macro !== undefined
                      ? `${
                          exp.improvement.f1_macro >= 0 ? "+" : ""
                        }${(exp.improvement.f1_macro * 100).toFixed(1)}%`
                      : "—"}
                  </td>

                  {/* Duration */}
                  <td className="px-4 py-3 text-slate-300">
                    {exp.completed_at && exp.started_at
                      ? formatDuration(
                          exp.started_at,
                          exp.completed_at
                        )
                      : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Empty state */}
        {experiments.length === 0 && (
          <div className="rounded-xl border border-dashed border-border p-10 text-center text-sm text-slate-500">
            No experiments found. Click "New Experiment" to create one.
          </div>
        )}
      </div>
    </div>
  );
}