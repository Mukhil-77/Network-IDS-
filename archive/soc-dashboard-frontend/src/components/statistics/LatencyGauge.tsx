interface LatencyGaugeProps {
  latencyMs: number;
  accuracy: number | null;
}

export function LatencyGauge({ latencyMs, accuracy }: LatencyGaugeProps) {
  return (
    <div className="grid grid-cols-2 gap-4">
      <div>
        <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Avg. Prediction Latency</p>
        <p className="mt-2 font-mono text-3xl font-semibold text-signal">{latencyMs.toFixed(1)}<span className="text-base text-slate-500"> ms</span></p>
      </div>
      <div>
        <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Detection Accuracy</p>
        <p className="mt-2 font-mono text-3xl font-semibold text-slate-100">
          {accuracy !== null ? `${(accuracy * 100).toFixed(1)}%` : "—"}
        </p>
        {accuracy === null && <p className="mt-1 text-xs text-slate-600">No model metadata synced yet</p>}
      </div>
    </div>
  );
}
