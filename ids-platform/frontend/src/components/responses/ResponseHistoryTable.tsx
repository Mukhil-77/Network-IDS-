import type { ResponseHistoryEntry } from "../../types/response";
import { formatTimestamp } from "../../utils/formatters";

interface ResponseHistoryTableProps {
  responses: ResponseHistoryEntry[];
  onRollback?: (responseId: string) => void;
  rollingBackId?: string;
  onRerun?: (response: { id: string; alert_id: string; action: string; mode: string }) => void;
  rerunningId?: string | null;
}

const STATUS_CLASSES: Record<string, string> = {
  success: "bg-severity-benign/15 text-severity-benign border-severity-benign/30",
  failed: "bg-severity-critical/15 text-severity-critical border-severity-critical/30",
  skipped: "bg-slate-500/15 text-slate-300 border-slate-500/30",
};

function StatusChip({ status }: { status: string }) {
  return (
    <span className={`inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium font-mono ${STATUS_CLASSES[status] ?? STATUS_CLASSES.skipped}`}>
      {status}
    </span>
  );
}

export function ResponseHistoryTable({ responses, onRollback, rollingBackId, onRerun, rerunningId }: ResponseHistoryTableProps) {
  if (responses.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-border p-10 text-center text-sm text-slate-500">
        No response actions recorded yet.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-border">
      <table className="w-full text-left text-sm">
        <thead className="border-b border-border bg-surface-raised text-xs uppercase tracking-wide text-slate-500">
          <tr>
            <th className="px-4 py-3 font-medium">Timestamp</th>
            <th className="px-4 py-3 font-medium">Alert</th>
            <th className="px-4 py-3 font-medium">Action</th>
            <th className="px-4 py-3 font-medium">Status</th>
            <th className="px-4 py-3 font-medium">Mode</th>
            <th className="px-4 py-3 font-medium">Operator</th>
            <th className="px-4 py-3 font-medium">Duration</th>
            <th className="px-4 py-3 font-medium">Actions</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {responses.map((response) => (
            <tr key={response.id} className="hover:bg-surface-raised/60">
              <td className="whitespace-nowrap px-4 py-2.5 font-mono text-xs text-slate-400">{formatTimestamp(response.timestamp)}</td>
              <td className="px-4 py-2.5 font-mono text-xs text-slate-500" title={response.alert_id}>{response.alert_id.slice(0, 8)}</td>
              <td className="px-4 py-2.5 font-medium text-slate-100">{response.action}</td>
              <td className="px-4 py-2.5"><StatusChip status={response.status} /></td>
              <td className="px-4 py-2.5">
                <span className={response.mode === "live" ? "text-severity-high" : "text-slate-400"}>{response.mode}</span>
              </td>
              <td className="px-4 py-2.5 text-slate-400">{response.operator}</td>
              <td className="px-4 py-2.5 font-mono text-slate-300">{response.execution_time_ms.toFixed(1)} ms</td>
              <td className="px-4 py-2.5">
                <div className="flex items-center gap-2">
                  {onRerun && (
                    <button
                      onClick={() => onRerun({ id: response.id, alert_id: response.alert_id, action: response.action, mode: response.mode })}
                      disabled={rerunningId === response.id}
                      className="rounded-md border border-border px-2 py-1 text-xs font-medium text-slate-300 hover:border-signal/50 hover:text-signal disabled:opacity-40"
                    >
                      {rerunningId === response.id ? "Re-running…" : "Re-run"}
                    </button>
                  )}
                  {response.rolled_back ? (
                    <span className="text-xs text-slate-600">rolled back</span>
                  ) : response.rollback_available && onRollback ? (
                    <button
                      onClick={() => onRollback(response.id)}
                      disabled={rollingBackId === response.id}
                      className="rounded-md border border-border px-2 py-1 text-xs font-medium text-slate-300 hover:border-signal/50 hover:text-signal disabled:opacity-40"
                    >
                      {rollingBackId === response.id ? "Rolling back…" : "Rollback"}
                    </button>
                  ) : (
                    <span className="text-xs text-slate-600">—</span>
                  )}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
