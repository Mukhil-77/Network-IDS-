import { severityColor } from "../../utils/severity";

interface SeverityBreakdownListProps {
  breakdown: Record<string, number>;
}

export function SeverityBreakdownList({ breakdown }: SeverityBreakdownListProps) {
  const entries = Object.entries(breakdown).sort((a, b) => b[1] - a[1]);
  const total = entries.reduce((sum, [, count]) => sum + count, 0) || 1;

  if (entries.length === 0) {
    return <p className="text-sm text-slate-500">No threats recorded yet.</p>;
  }

  return (
    <div className="space-y-2">
      {entries.map(([severity, count]) => (
        <div key={severity} className="flex items-center gap-3 text-sm">
          <span className="w-16 shrink-0 text-slate-300">{severity}</span>
          <div className="h-2 flex-1 overflow-hidden rounded-full bg-surface-overlay">
            <div
              className="h-full rounded-full"
              style={{ width: `${(count / total) * 100}%`, backgroundColor: severityColor(severity) }}
            />
          </div>
          <span className="w-10 shrink-0 text-right font-mono text-slate-400">{count}</span>
        </div>
      ))}
    </div>
  );
}
