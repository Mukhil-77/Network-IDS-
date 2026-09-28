import { useDeploymentMetrics } from "../../hooks/useDeploymentMetrics";

export function DeploymentMetricsCard() {
  const query = useDeploymentMetrics();

if (query.isLoading) {
    return (
      <div className="rounded-xl border border-border bg-surface-raised p-4">
        <div className="animate-pulse space-y-4">
          <div className="h-4 bg-slate-700 rounded w-1/4" />
          <div className="grid grid-cols-4 gap-4">
            {([1, 2, 3, 4] as const).map((i) => (
              <div key={i} className="h-20 bg-slate-700 rounded" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (query.isError) {
    return (
      <div className="rounded-xl border border-border bg-surface-raised p-4 text-center text-slate-500">
        Failed to load deployment metrics.
      </div>
    );
  }

  if (!query.data) {
    return (
      <div className="rounded-xl border border-border bg-surface-raised p-4 text-center text-slate-500">
        Loading deployment metrics...
      </div>
    );
  }

  const metrics = query.data;

  return (
    <div className="rounded-xl border border-border bg-surface-raised p-4">
      <h2 className="mb-4 text-sm font-medium text-slate-300">Deployment Metrics</h2>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <div className="bg-surface p-3 rounded-lg">
          <dt className="text-xs text-slate-500">Uptime</dt>
          <dd className="font-mono text-slate-200">
            {Math.floor(metrics.uptime_seconds / 3600)}h {Math.floor((metrics.uptime_seconds % 3600) / 60)}m
          </dd>
        </div>
        <div className="bg-surface p-3 rounded-lg">
          <dt className="text-xs text-slate-500">Model Load</dt>
          <dd className="font-mono text-slate-200">{metrics.model_load_time_ms.toFixed(0)} ms</dd>
        </div>
        <div className="bg-surface p-3 rounded-lg">
          <dt className="text-xs text-slate-500">Memory</dt>
          <dd className="font-mono text-slate-200">{Math.round(metrics.system.memory_mb)} MB</dd>
        </div>
        <div className="bg-surface p-3 rounded-lg">
          <dt className="text-xs text-slate-500">CPU</dt>
          <dd className="font-mono text-slate-200">{metrics.system.cpu_percent.toFixed(1)}%</dd>
        </div>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-4 md:grid-cols-4">
        <div className="bg-surface p-3 rounded-lg">
          <dt className="text-xs text-slate-500">P50 Latency</dt>
          <dd className="font-mono text-slate-200">{metrics.latency.p50.toFixed(1)} ms</dd>
        </div>
        <div className="bg-surface p-3 rounded-lg">
          <dt className="text-xs text-slate-500">P95 Latency</dt>
          <dd className="font-mono text-slate-200">{metrics.latency.p95.toFixed(1)} ms</dd>
        </div>
        <div className="bg-surface p-3 rounded-lg">
          <dt className="text-xs text-slate-500">P99 Latency</dt>
          <dd className="font-mono text-slate-200">{metrics.latency.p99.toFixed(1)} ms</dd>
        </div>
        <div className="bg-surface p-3 rounded-lg">
          <dt className="text-xs text-slate-500">Throughput</dt>
          <dd className="font-mono text-slate-200">{metrics.throughput.flows_per_second.toFixed(1)} flows/s</dd>
        </div>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-4 md:grid-cols-4">
        <div className="bg-surface p-3 rounded-lg">
          <dt className="text-xs text-slate-500">Accuracy</dt>
          <dd className="font-mono text-slate-200">{(metrics.detection.accuracy * 100).toFixed(1)}%</dd>
        </div>
        <div className="bg-surface p-3 rounded-lg">
          <dt className="text-xs text-slate-500">Precision</dt>
          <dd className="font-mono text-slate-200">{(metrics.detection.precision * 100).toFixed(1)}%</dd>
        </div>
        <div className="bg-surface p-3 rounded-lg">
          <dt className="text-xs text-slate-500">Recall</dt>
          <dd className="font-mono text-slate-200">{(metrics.detection.recall * 100).toFixed(1)}%</dd>
        </div>
        <div className="bg-surface p-3 rounded-lg">
          <dt className="text-xs text-slate-500">F1 Score</dt>
          <dd className="font-mono text-slate-200">{(metrics.detection.f1 * 100).toFixed(1)}%</dd>
        </div>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-4 md:grid-cols-4">
        <div className="bg-surface p-3 rounded-lg">
          <dt className="text-xs text-slate-500">FPR</dt>
          <dd className="font-mono text-slate-200">{(metrics.detection.fpr * 100).toFixed(2)}%</dd>
        </div>
        <div className="bg-surface p-3 rounded-lg">
          <dt className="text-xs text-slate-500">FNR</dt>
          <dd className="font-mono text-slate-200">{(metrics.detection.fnr * 100).toFixed(2)}%</dd>
        </div>
        <div className="bg-surface p-3 rounded-lg">
          <dt className="text-xs text-slate-500">MCC</dt>
          <dd className="font-mono text-slate-200">{metrics.detection.f1.toFixed(3)}</dd>
        </div>
        <div className="bg-surface p-3 rounded-lg">
          <dt className="text-xs text-slate-500">Avg Latency</dt>
          <dd className="font-mono text-slate-200">{metrics.detection.avg_latency_ms.toFixed(1)} ms</dd>
        </div>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-4 md:grid-cols-4">
        <div className="bg-surface p-3 rounded-lg">
          <dt className="text-xs text-slate-500">TP</dt>
          <dd className="font-mono text-emerald-400">{metrics.detection.true_positives}</dd>
        </div>
        <div className="bg-surface p-3 rounded-lg">
          <dt className="text-xs text-slate-500">FP</dt>
          <dd className="font-mono text-red-400">{metrics.detection.false_positives}</dd>
        </div>
        <div className="bg-surface p-3 rounded-lg">
          <dt className="text-xs text-slate-500">TN</dt>
          <dd className="font-mono text-emerald-400">{metrics.detection.true_negatives}</dd>
        </div>
        <div className="bg-surface p-3 rounded-lg">
          <dt className="text-xs text-slate-500">FN</dt>
          <dd className="font-mono text-red-400">{metrics.detection.false_negatives}</dd>
        </div>
      </div>
    </div>
  );
}