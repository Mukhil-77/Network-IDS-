import { useApiHealth, useSystemHealth, useSystemStats } from "../hooks/useSystemHealth";
import { useModelInfo } from "../hooks/useModelInfo";
import { StatCard } from "../components/dashboard/StatCard";
import { TelemetryCard, formatBytes } from "../components/system/TelemetryCard";
import { useTelemetrySeries } from "../components/system/useTelemetrySeries";
import { CardSkeleton } from "../components/common/LoadingSkeleton";
import { ErrorState } from "../components/common/ErrorState";

const CPU_COLOR = "#22d3ee";
const MEMORY_COLOR = "#a78bfa";
const DISK_COLOR = "#34d399";
const NETWORK_COLOR = "#f472b6";
const PROCESS_COLOR = "#fbbf24";
const GPU_COLOR = "#60a5fa";

export default function SystemHealth() {
  const apiHealthQuery = useApiHealth();
  const systemHealthQuery = useSystemHealth();
  const statsQuery = useSystemStats();
  const modelInfoQuery = useModelInfo();

  // Rolling histories for the task-manager sparklines (60 points @ 2 s = 2 min).
  const cpuSeries = useTelemetrySeries(statsQuery.data?.cpu.percent);
  const memorySeries = useTelemetrySeries(statsQuery.data?.memory.percent);
  const diskSeries = useTelemetrySeries(statsQuery.data?.disk.percent);
  const netRecvSeries = useTelemetrySeries(statsQuery.data?.network.bytes_recv_per_sec);
  const processSeries = useTelemetrySeries(statsQuery.data?.process.cpu_percent);
  const gpuSeries = useTelemetrySeries(statsQuery.data?.gpu?.utilization_percent);

  const backendUp = apiHealthQuery.isSuccess;
  const dbUp = systemHealthQuery.isSuccess; // /system/health only succeeds if the DB query it runs succeeds
  const stats = statsQuery.data;

  return (
    <div className="space-y-6">
      <h1 className="text-lg font-semibold text-slate-100">System Health</h1>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <StatCard
          label="Backend Status"
          value={apiHealthQuery.isLoading ? "…" : backendUp ? "Online" : "Unreachable"}
          accent={backendUp ? "signal" : "critical"}
        />
        <StatCard
          label="Database Status"
          value={systemHealthQuery.isLoading ? "…" : dbUp ? "Connected" : "Unreachable"}
          accent={dbUp ? "signal" : "critical"}
        />
        <StatCard
          label="Model Status"
          value={systemHealthQuery.data?.model_status ?? "…"}
          accent={systemHealthQuery.data?.model_status === "loaded" ? "signal" : "critical"}
          hint={systemHealthQuery.data?.model_version ?? undefined}
        />
        <StatCard
          label="Detection Rate"
          value={systemHealthQuery.data ? `${systemHealthQuery.data.alerts_last_minute}/min` : "…"}
          hint="Alerts in the last minute"
        />
      </div>

      <div>
        <h2 className="mb-3 text-sm font-medium text-slate-300">Live System Telemetry</h2>

        {statsQuery.isLoading && <CardSkeleton />}
        {statsQuery.isError && (
          <ErrorState
            message="Couldn't load OS telemetry. Is the backend running with psutil available?"
            onRetry={() => statsQuery.refetch()}
          />
        )}

        {stats && (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <TelemetryCard
              title="CPU Usage"
              percent={stats.cpu.percent}
              color={CPU_COLOR}
              detail={`${stats.cpu.logical_count} logical / ${stats.cpu.physical_count} physical cores`}
              footer={stats.cpu.per_core_percent.length ? `max core ${Math.max(...stats.cpu.per_core_percent).toFixed(0)}%` : undefined}
              series={cpuSeries}
            />

            <TelemetryCard
              title="Memory Usage"
              percent={stats.memory.percent}
              color={MEMORY_COLOR}
              detail={`${formatBytes(stats.memory.used_bytes)} of ${formatBytes(stats.memory.total_bytes)}`}
              footer={
                stats.memory.swap_total_bytes > 0
                  ? `swap ${formatBytes(stats.memory.swap_used_bytes)} / ${formatBytes(stats.memory.swap_total_bytes)}`
                  : undefined
              }
              series={memorySeries}
            />

            <TelemetryCard
              title="Disk Usage"
              percent={stats.disk.percent}
              color={DISK_COLOR}
              detail={`${formatBytes(stats.disk.used_bytes)} of ${formatBytes(stats.disk.total_bytes)}`}
              footer={`${formatBytes(stats.disk.free_bytes)} free`}
              series={diskSeries}
            />

            <TelemetryCard
              title="Network"
              percent={null}
              color={NETWORK_COLOR}
              detail="Throughput per second"
              footer={`↓ ${formatBytes(stats.network.bytes_recv_per_sec)}/s · ↑ ${formatBytes(stats.network.bytes_sent_per_sec)}/s`}
              series={netRecvSeries}
            />

            <TelemetryCard
              title="SOC Backend Process"
              percent={Math.min(100, stats.process.cpu_percent)}
              color={PROCESS_COLOR}
              detail={`CPU ${stats.process.cpu_percent.toFixed(1)}% · ${stats.process.threads} threads`}
              footer={`RSS ${formatBytes(stats.process.memory_rss_bytes)}`}
              series={processSeries}
            />

            {stats.gpu && (
              <TelemetryCard
                title="GPU"
                percent={stats.gpu.utilization_percent}
                color={GPU_COLOR}
                detail={stats.gpu.name}
                footer={`VRAM ${formatBytes(stats.gpu.memory_used_mb * 1024 * 1024)} / ${formatBytes(stats.gpu.memory_total_mb * 1024 * 1024)}`}
                series={gpuSeries}
              />
            )}
          </div>
        )}
      </div>

      <div className="rounded-xl border border-border bg-surface-raised p-4">
        <h2 className="mb-4 text-sm font-medium text-slate-300">Active Model</h2>
        {modelInfoQuery.isLoading && <CardSkeleton />}
        {modelInfoQuery.isError && (
          <ErrorState message="No model currently loaded." onRetry={() => modelInfoQuery.refetch()} />
        )}
        {modelInfoQuery.data && (
          <dl className="grid grid-cols-2 gap-y-2 text-sm md:grid-cols-4">
            <dt className="text-slate-500">Name</dt>
            <dd className="font-mono text-slate-200">{modelInfoQuery.data.model_name}</dd>
            <dt className="text-slate-500">Version</dt>
            <dd className="font-mono text-slate-200">{modelInfoQuery.data.version}</dd>
            <dt className="text-slate-500">Trained</dt>
            <dd className="font-mono text-slate-200">{modelInfoQuery.data.training_date}</dd>
            <dt className="text-slate-500">Accuracy</dt>
            <dd className="font-mono text-slate-200">{(modelInfoQuery.data.accuracy * 100).toFixed(1)}%</dd>
            <dt className="text-slate-500">Features</dt>
            <dd className="font-mono text-slate-200">{modelInfoQuery.data.num_features}</dd>
            <dt className="text-slate-500">PCA components</dt>
            <dd className="font-mono text-slate-200">{modelInfoQuery.data.pca_components}</dd>
            <dt className="text-slate-500">scikit-learn</dt>
            <dd className="font-mono text-slate-200">{modelInfoQuery.data.sklearn_version}</dd>
          </dl>
        )}
      </div>
    </div>
  );
}