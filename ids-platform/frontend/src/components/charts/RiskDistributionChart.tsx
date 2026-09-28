import { useQuery } from "@tanstack/react-query";
import { apiClient } from "../../services/apiClient";

export function RiskDistributionChart() {
  const query = useQuery({
    queryKey: ["risk", "distribution"],
    queryFn: async () => {
      const { data } = await apiClient.get<Record<string, number>>("/analytics/risk-distribution");
      return data;
    },
    refetchInterval: 60_000,
  });

  if (query.isLoading) {
    return <div className="h-64 bg-surface p-4 rounded-xl animate-pulse" />;
  }

  if (query.isError || !query.data) {
    return <div className="h-64 bg-surface p-4 rounded-xl text-center text-slate-500">No risk data available</div>;
  }

  const data = query.data;
  const total = Object.values(data).reduce((a, b) => a + b, 0);
  const entries = Object.entries(data).sort((a, b) => b[1] - a[1]);

  return (
    <div className="rounded-xl border border-border bg-surface-raised p-4">
      <h3 className="mb-4 text-sm font-medium text-slate-300">Risk Distribution</h3>
      <div className="space-y-3">
        {entries.map(([level, count]) => (
          <div key={level} className="flex items-center gap-3">
            <span className={`text-xs font-medium w-20 capitalize ${getRiskColor(level)}`}>
              {level}
            </span>
            <div className="flex-1 h-3 bg-slate-800 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full ${getRiskBarColor(level)}`}
                style={{ width: total > 0 ? `${(count / total) * 100}%` : "0%" }}
              />
            </div>
            <span className="text-xs font-mono text-slate-400 w-10 text-right">
              {total > 0 ? `${((count / total) * 100).toFixed(1)}%` : "0%"}
            </span>
          </div>
        ))}
      </div>
      <div className="mt-3 text-xs text-slate-500 text-right">
        Total: {total} events
      </div>
    </div>
  );
}

function getRiskColor(level: string): string {
  switch (level.toLowerCase()) {
    case "critical": return "text-red-400";
    case "high": return "text-orange-400";
    case "medium": return "text-yellow-400";
    case "guarded": return "text-blue-400";
    case "low": return "text-green-400";
    default: return "text-slate-400";
  }
}

function getRiskBarColor(level: string): string {
  switch (level.toLowerCase()) {
    case "critical": return "bg-red-500";
    case "high": return "bg-orange-500";
    case "medium": return "bg-yellow-500";
    case "guarded": return "bg-blue-500";
    case "low": return "bg-green-500";
    default: return "bg-slate-500";
  }
}