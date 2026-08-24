import type { SystemHealth } from "../../types/health";

export function SystemHealthSummary({ health }: { health: SystemHealth }) {
  const isHealthy = health.status === "healthy";

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <span className={`h-2.5 w-2.5 rounded-full ${isHealthy ? "bg-severity-benign" : "bg-severity-high"}`} />
        <span className="text-sm font-medium text-slate-100">
          {isHealthy ? "All systems operational" : "Degraded"}
        </span>
      </div>
      <dl className="grid grid-cols-2 gap-y-1.5 text-sm">
        <dt className="text-slate-500">Model</dt>
        <dd className="text-right font-mono text-slate-300">{health.model_status}</dd>
        <dt className="text-slate-500">Model version</dt>
        <dd className="text-right font-mono text-slate-300">{health.model_version ?? "—"}</dd>
        <dt className="text-slate-500">Alerts (last min)</dt>
        <dd className="text-right font-mono text-slate-300">{health.alerts_last_minute}</dd>
      </dl>
    </div>
  );
}
