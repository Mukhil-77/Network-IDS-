interface ResponseTimeChartProps {
  averageResponseTimeSeconds: number | null;
  averageDetectionTimeMs: number;
}

export function ResponseTimeChart({ averageResponseTimeSeconds, averageDetectionTimeMs }: ResponseTimeChartProps) {
  return (
    <div className="grid grid-cols-2 gap-4">
      <div>
        <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Avg. Detection Time</p>
        <p className="mt-2 font-mono text-3xl font-semibold text-signal">
          {averageDetectionTimeMs.toFixed(1)}<span className="text-base text-slate-500"> ms</span>
        </p>
      </div>
      <div>
        <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Avg. Response Time</p>
        <p className="mt-2 font-mono text-3xl font-semibold text-slate-100">
          {averageResponseTimeSeconds !== null ? (
            <>{averageResponseTimeSeconds.toFixed(1)}<span className="text-base text-slate-500"> s</span></>
          ) : (
            "—"
          )}
        </p>
        {averageResponseTimeSeconds === null && <p className="mt-1 text-xs text-slate-600">No responses recorded yet</p>}
      </div>
    </div>
  );
}
