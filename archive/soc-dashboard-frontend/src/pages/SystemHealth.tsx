import { useApiHealth, useSystemHealth } from "../hooks/useSystemHealth";
import { useModelInfo } from "../hooks/useModelInfo";
import { StatCard } from "../components/dashboard/StatCard";
import { NotAvailableCard } from "../components/common/NotAvailableCard";
import { CardSkeleton } from "../components/common/LoadingSkeleton";
import { ErrorState } from "../components/common/ErrorState";

export default function SystemHealth() {
  const apiHealthQuery = useApiHealth();
  const systemHealthQuery = useSystemHealth();
  const modelInfoQuery = useModelInfo();

  const backendUp = apiHealthQuery.isSuccess;
  const dbUp = systemHealthQuery.isSuccess; // /system/health only succeeds if the DB query it runs succeeds

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

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        {/* CPU/Memory/Disk/Packet Rate need OS-level telemetry the backend
            doesn't expose yet (Milestone 6 scope) - shown honestly rather
            than fabricated. See docs/FRONTEND_ARCHITECTURE.md. */}
        <NotAvailableCard label="CPU Usage" />
        <NotAvailableCard label="Memory Usage" />
        <NotAvailableCard label="Disk Usage" />
        <NotAvailableCard label="Packet Rate" />
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
