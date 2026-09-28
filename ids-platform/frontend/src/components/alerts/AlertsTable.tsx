import type { AlertRow, AlertFilters } from "../../types/alert";
import { SeverityBadge, StatusBadge } from "../common/Badge";
import { formatTimestamp } from "../../utils/formatters";
import { SHAPExplanationCard } from "./SHAPExplanationCard";

function threatTagBg(tag: string) {
  switch (tag) {
    case "Trusted":
      return "bg-green-100 text-green-800";
    case "Known Malicious":
      return "bg-red-100 text-red-800";
    case "Suspicious":
      return "bg-orange-100 text-orange-800";
    default:
      return "bg-slate-100 text-slate-700";
  }
}

function threatTagFg(tag: string) {
  switch (tag) {
    case "Trusted":
      return "text-green-800";
    case "Known Malicious":
      return "text-red-800";
    case "Suspicious":
      return "text-orange-800";
    default:
      return "text-slate-700";
  }
}

function priorityBg(priority: string) {
  switch (priority) {
    case "P1_CRITICAL":
      return "bg-red-100 text-red-800";
    case "P2_HIGH":
      return "bg-orange-100 text-orange-800";
    case "P3_MEDIUM":
      return "bg-yellow-100 text-yellow-800";
    case "P4_LOW":
      return "bg-slate-100 text-slate-800";
    default:
      return "bg-slate-100 text-slate-700";
  }
}

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
  { key: "risk_score", label: "Risk" },
  { key: "priority", label: "Priority" },
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
              <td className="px-4 py-2.5 font-mono text-slate-300">{alert.risk_score}</td>
              <td className="px-4 py-2.5">
                {alert.priority && (
                  <span
                    className={`inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium ${priorityBg(alert.priority)}`}
                  >
                    {alert.priority}
                  </span>
                )}
              </td>
              <td className="px-4 py-2.5 font-mono text-slate-300">{alert.source_ip}</td>
              <td className="px-4 py-2.5 font-mono text-slate-300">{alert.destination_ip}</td>
              <td className="px-4 py-2.5 text-slate-400">{alert.protocol}</td>
              <td className="px-4 py-2.5">
                <StatusBadge status={alert.status} />
                {alert.threat_tag && alert.threat_tag !== "Unknown" && (
                  <span
                    className="inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium ml-2"
                    style={{
                      background: threatTagBg(alert.threat_tag),
                      color: threatTagFg(alert.threat_tag),
                    }}
                  >
                    {alert.threat_tag}
                  </span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}