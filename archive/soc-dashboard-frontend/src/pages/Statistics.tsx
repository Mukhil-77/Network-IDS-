import { useStatistics, useTopAttacks } from "../hooks/useStatistics";
import { ThreatsOverTimeChart } from "../components/charts/ThreatsOverTimeChart";
import { ThreatsByTypeChart } from "../components/charts/ThreatsByTypeChart";
import { ThreatsBySeverityChart } from "../components/charts/ThreatsBySeverityChart";
import { TopSourceIPsChart } from "../components/charts/TopSourceIPsChart";
import { LatencyGauge } from "../components/statistics/LatencyGauge";
import { NotAvailableCard } from "../components/common/NotAvailableCard";
import { ChartSkeleton } from "../components/common/LoadingSkeleton";
import { ErrorState } from "../components/common/ErrorState";

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-border bg-surface-raised p-4">
      <h2 className="mb-4 text-sm font-medium text-slate-300">{title}</h2>
      {children}
    </div>
  );
}

export default function Statistics() {
  const statsQuery = useStatistics(60);
  const topAttacksQuery = useTopAttacks(10);

  if (statsQuery.isError) {
    return <ErrorState message="Couldn't load statistics." onRetry={() => statsQuery.refetch()} />;
  }

  const stats = statsQuery.data;

  return (
    <div className="space-y-6">
      <h1 className="text-lg font-semibold text-slate-100">Statistics</h1>

      <Panel title="Threats per Hour (last 60 min, by minute)">
        {statsQuery.isLoading ? <ChartSkeleton /> : <ThreatsOverTimeChart data={stats!.threats_per_minute} />}
      </Panel>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Panel title="Threats by Type">
          {statsQuery.isLoading ? <ChartSkeleton /> : <ThreatsByTypeChart data={stats!.threats_by_type} />}
        </Panel>
        <Panel title="Threats by Severity">
          {statsQuery.isLoading ? <ChartSkeleton /> : <ThreatsBySeverityChart data={stats!.threats_by_severity} />}
        </Panel>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Panel title="Top Source IPs">
          {statsQuery.isLoading ? <ChartSkeleton /> : <TopSourceIPsChart data={stats!.top_source_ips} />}
        </Panel>
        <Panel title="Prediction Latency & Detection Accuracy">
          {statsQuery.isLoading ? (
            <ChartSkeleton />
          ) : (
            <LatencyGauge latencyMs={stats!.average_prediction_latency_ms} accuracy={stats!.detection_accuracy} />
          )}
        </Panel>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {/* Backend has no OS-level telemetry endpoint (Milestone 6 never
            built one) - shown honestly as unavailable rather than faked. */}
        <NotAvailableCard label="System Load" />
        <div className="rounded-xl border border-border bg-surface-raised p-4 md:col-span-2">
          <h2 className="mb-3 text-sm font-medium text-slate-300">Most Frequent Attack Types</h2>
          <ul className="divide-y divide-border text-sm">
            {topAttacksQuery.data?.map((a) => (
              <li key={a.attack_type} className="flex items-center justify-between py-2">
                <span className="text-slate-200">{a.attack_type}</span>
                <span className="font-mono text-slate-400">
                  {a.total_count} · avg {a.avg_confidence.toFixed(1)}%
                </span>
              </li>
            ))}
            {topAttacksQuery.data?.length === 0 && <li className="py-2 text-slate-500">No attacks recorded yet.</li>}
          </ul>
        </div>
      </div>
    </div>
  );
}
