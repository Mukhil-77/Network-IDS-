import { useStatistics } from "../hooks/useStatistics";
import { useSystemHealth } from "../hooks/useSystemHealth";
import { useWebSocketAlerts } from "../context/WebSocketContext";
import { StatCard } from "../components/dashboard/StatCard";
import { SeverityBreakdownList } from "../components/dashboard/SeverityBreakdownList";
import { SystemHealthSummary } from "../components/dashboard/SystemHealthSummary";
import { CaptureControl } from "../components/dashboard/CaptureControl";
import { ThreatsByTypeChart } from "../components/charts/ThreatsByTypeChart";
import { CardSkeleton, ChartSkeleton } from "../components/common/LoadingSkeleton";
import { ErrorState } from "../components/common/ErrorState";

export default function Dashboard() {
  // window_minutes=1440 (24h) so "Threats Today" is derived from real
  // per-minute buckets the backend already computes - not a separate
  // endpoint that doesn't exist.
  const statsQuery = useStatistics(1440);
  const healthQuery = useSystemHealth();
  const { liveAlerts } = useWebSocketAlerts();

  if (statsQuery.isError) {
    return <ErrorState message="Couldn't load statistics." onRetry={() => statsQuery.refetch()} />;
  }

  const stats = statsQuery.data;
  const threatsToday = stats?.threats_per_minute.reduce((sum, p) => sum + p.count, 0) ?? 0;
  // "Active" here means alerts received this session with status "new" -
  // the backend has no dedicated status-count endpoint (Milestone 6 didn't
  // build one), so this is a client-side approximation over the live feed,
  // not a full historical count. See docs/FRONTEND_ARCHITECTURE.md.
  const activeAlerts = liveAlerts.filter((a) => a.status === "new").length;

  return (
    <div className="space-y-6">
      <h1 className="text-lg font-semibold text-slate-100">Dashboard</h1>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-5">
        {statsQuery.isLoading ? (
          Array.from({ length: 5 }).map((_, i) => <CardSkeleton key={i} />)
        ) : (
          <>
            <StatCard label="Total Threats" value={String(stats!.threat_count)} />
            <StatCard label="Active Alerts (session)" value={String(activeAlerts)} accent="signal" />
            <StatCard label="Threats Today" value={String(threatsToday)} />
            <StatCard 
              label="Avg Prediction Time" 
              value={`${stats!.average_prediction_latency_ms?.toFixed(2) ?? "—"} ms`} 
            />
            <CaptureControl />
          </>
        )}
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="rounded-xl border border-border bg-surface-raised p-4 lg:col-span-2">
          <h2 className="mb-4 text-sm font-medium text-slate-300">Threats by Type</h2>
          {statsQuery.isLoading ? <ChartSkeleton /> : <ThreatsByTypeChart data={stats!.threats_by_type} />}
        </div>

        <div className="rounded-xl border border-border bg-surface-raised p-4">
          <h2 className="mb-4 text-sm font-medium text-slate-300">Threats by Severity</h2>
          {statsQuery.isLoading ? (
            <CardSkeleton />
          ) : (
            <SeverityBreakdownList breakdown={stats!.threats_by_severity} />
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="rounded-xl border border-border bg-surface-raised p-4">
          <h2 className="mb-4 text-sm font-medium text-slate-300">Detection Accuracy</h2>
          <p className="font-mono text-3xl font-semibold text-slate-100">
            {stats?.detection_accuracy !== null && stats?.detection_accuracy !== undefined
              ? `${(stats.detection_accuracy * 100).toFixed(1)}%`
              : "—"}
          </p>
          <p className="mt-1 text-xs text-slate-500">Model's own evaluated accuracy, not a live-traffic figure</p>
        </div>

        <div className="rounded-xl border border-border bg-surface-raised p-4 lg:col-span-2">
          <h2 className="mb-4 text-sm font-medium text-slate-300">System Health</h2>
          {healthQuery.isLoading && <CardSkeleton />}
          {healthQuery.isError && <ErrorState message="Couldn't load system health." onRetry={() => healthQuery.refetch()} />}
          {healthQuery.data && <SystemHealthSummary health={healthQuery.data} />}
        </div>
      </div>
    </div>
  );
}
