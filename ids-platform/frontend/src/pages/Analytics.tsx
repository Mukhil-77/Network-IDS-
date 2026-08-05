import { useAnalyticsOverview, useAnalyticsTrends } from "../hooks/useAnalytics";
import { ThreatsOverTimeChart } from "../components/charts/ThreatsOverTimeChart";
import { ThreatsByTypeChart } from "../components/charts/ThreatsByTypeChart";
import { ThreatsBySeverityChart } from "../components/charts/ThreatsBySeverityChart";
import { TopSourceIPsChart } from "../components/charts/TopSourceIPsChart";
import { ResponseTimeChart } from "../components/charts/ResponseTimeChart";
import { ChartSkeleton } from "../components/common/LoadingSkeleton";
import { ErrorState } from "../components/common/ErrorState";
import { NotAvailableCard } from "../components/common/NotAvailableCard";

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-border bg-surface-raised p-4">
      <h2 className="mb-4 text-sm font-medium text-slate-300">{title}</h2>
      {children}
    </div>
  );
}

export default function Analytics() {
  const overviewQuery = useAnalyticsOverview(30);
  const trendsQuery = useAnalyticsTrends(30, 7);

  if (overviewQuery.isError) {
    return <ErrorState message="Couldn't load analytics." onRetry={() => overviewQuery.refetch()} />;
  }
  const data = overviewQuery.data;

  return (
    <div className="space-y-6">
      <h1 className="text-lg font-semibold text-slate-100">Analytics</h1>

      <Panel title="Attack Timeline (30 days) + 7-day Forecast">
        {overviewQuery.isLoading ? (
          <ChartSkeleton />
        ) : (
          <ThreatsOverTimeChart
            data={[...data!.attack_timeline.map((p) => ({ minute: p.date, count: p.count })),
                   ...(trendsQuery.data?.forecast.map((p) => ({ minute: p.date, count: p.count })) ?? [])]}
          />
        )}
      </Panel>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Panel title="Top Attack Types">
          {overviewQuery.isLoading ? <ChartSkeleton /> : <ThreatsByTypeChart data={data!.top_attack_types} />}
        </Panel>
        <Panel title="Severity Distribution">
          {overviewQuery.isLoading ? <ChartSkeleton /> : <ThreatsBySeverityChart data={data!.severity_distribution} />}
        </Panel>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Panel title="Top Source IPs">
          {overviewQuery.isLoading ? (
            <ChartSkeleton />
          ) : (
            <TopSourceIPsChart data={data!.top_source_ips.map((p) => ({ source_ip: p.source_ip, count: p.count }))} />
          )}
        </Panel>
        <Panel title="Top Destination IPs">
          {overviewQuery.isLoading ? (
            <ChartSkeleton />
          ) : (
            <TopSourceIPsChart data={data!.top_destination_ips.map((p) => ({ source_ip: p.destination_ip, count: p.count }))} />
          )}
        </Panel>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <Panel title="Detection & Response Time">
          {overviewQuery.isLoading ? <ChartSkeleton /> : (
            <ResponseTimeChart
              averageDetectionTimeMs={data!.average_detection_time_ms}
              averageResponseTimeSeconds={data!.average_response_time_seconds}
            />
          )}
        </Panel>
        <div className="rounded-xl border border-border bg-surface-raised p-4">
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Detection Accuracy</p>
          <p className="mt-2 font-mono text-2xl font-semibold text-slate-100">
            {data?.detection_accuracy !== null && data?.detection_accuracy !== undefined ? `${(data.detection_accuracy * 100).toFixed(1)}%` : "—"}
          </p>
        </div>
        {/* Honest placeholder - see backend/analytics/analytics_service.py's docstring: computing a real
            false-positive rate needs ground-truth labels this platform doesn't collect yet. */}
        <NotAvailableCard label="False Positive Rate" reason="Requires labeled ground truth (not yet collected)" />
      </div>
    </div>
  );
}
