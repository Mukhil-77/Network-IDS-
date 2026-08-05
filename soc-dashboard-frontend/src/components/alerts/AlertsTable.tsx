import type { AlertRow, AlertFilters } from "../../types/alert";
import { SeverityBadge, StatusBadge } from "../common/Badge";
import { formatTimestamp } from "../../utils/formatters";

interface AlertsTableProps {
  alerts: AlertRow[];
  sortBy: AlertFilters["sort_by"];
  sortDesc: boolean;
  onSortChange: (sortBy: NonNullable<AlertFilters["sort_by"]>) => void;
}

interface ColumnDef {
  key: NonNullable<AlertFilters["sort_by"]> | null;
  label: string;
}

const COLUMNS: ColumnDef[] = [
  { key: "timestamp", label: "Timestamp" },
  { key: null, label: "Attack Type" },
  { key: "severity", label: "Severity" },
  { key: "confidence", label: "Confidence" },
  { key: null, label: "Source IP" },
  { key: null, label: "Destination IP" },
  { key: null, label: "Protocol" },
  { key: null, label: "Status" },
];

export function AlertsTable({ alerts, sortBy, sortDesc, onSortChange }: AlertsTableProps) {
  if (alerts.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-border p-10 text-center text-sm text-slate-500">
        No alerts match the current filters. Widen your filters, or wait — new detections stream in live.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-border">
      <table className="w-full text-left text-sm">
        <thead className="border-b border-border bg-surface-raised text-xs uppercase tracking-wide text-slate-500">
          <tr>
            {COLUMNS.map((col) => (
              <th key={col.label} className="px-4 py-3 font-medium">
                {col.key ? (
                  <button
                    onClick={() => onSortChange(col.key as NonNullable<AlertFilters["sort_by"]>)}
                    className="flex items-center gap-1 hover:text-signal"
                  >
                    {col.label}
                    {sortBy === col.key && <span>{sortDesc ? "↓" : "↑"}</span>}
                  </button>
                ) : (
                  col.label
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {alerts.map((alert) => (
            <tr key={alert.id} className="hover:bg-surface-raised/60">
              <td className="whitespace-nowrap px-4 py-2.5 font-mono text-xs text-slate-400">
                {formatTimestamp(alert.timestamp)}
              </td>
              <td className="px-4 py-2.5 font-medium text-slate-100">{alert.attack_type}</td>
              <td className="px-4 py-2.5">
                <SeverityBadge severity={alert.severity} />
              </td>
              <td className="px-4 py-2.5 font-mono text-slate-300">{alert.confidence.toFixed(1)}%</td>
              <td className="px-4 py-2.5 font-mono text-slate-300">{alert.source_ip}</td>
              <td className="px-4 py-2.5 font-mono text-slate-300">{alert.destination_ip}</td>
              <td className="px-4 py-2.5 text-slate-400">{alert.protocol}</td>
              <td className="px-4 py-2.5">
                <StatusBadge status={alert.status} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
