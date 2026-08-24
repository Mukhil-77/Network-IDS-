import type { FlowRow } from "../../types/flow";
import { formatBytes, formatTimestamp } from "../../utils/formatters";
import { SeverityBadge } from "../common/Badge";

interface FlowsTableProps {
  flows: FlowRow[];
  // flow_id -> attack_type, built from recent alerts (see pages/Flows.tsx).
  // FlowHistory (backend/database/models.py) has no attack_type column of
  // its own - only Alert does, joined by flow_id - so "Prediction" here is
  // a best-effort match against recently-seen alerts, not a guaranteed
  // field. Flows older than the alert lookback window show "—".
  predictionByFlowId: Map<string, { attack_type: string; severity: string }>;
}

export function FlowsTable({ flows, predictionByFlowId }: FlowsTableProps) {
  if (flows.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-border p-10 text-center text-sm text-slate-500">
        No flows recorded yet.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-border">
      <table className="w-full text-left text-sm">
        <thead className="border-b border-border bg-surface-raised text-xs uppercase tracking-wide text-slate-500">
          <tr>
            <th className="px-4 py-3 font-medium">Flow ID</th>
            <th className="px-4 py-3 font-medium">Source</th>
            <th className="px-4 py-3 font-medium">Destination</th>
            <th className="px-4 py-3 font-medium">Protocol</th>
            <th className="px-4 py-3 font-medium">Packets</th>
            <th className="px-4 py-3 font-medium">Bytes</th>
            <th className="px-4 py-3 font-medium">Started</th>
            <th className="px-4 py-3 font-medium">Prediction</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {flows.map((flow) => {
            const prediction = predictionByFlowId.get(flow.id);
            return (
              <tr key={flow.id} className="hover:bg-surface-raised/60">
                <td className="px-4 py-2.5 font-mono text-xs text-slate-500" title={flow.id}>
                  {flow.id.slice(0, 8)}
                </td>
                <td className="px-4 py-2.5 font-mono text-slate-300">
                  {flow.source_ip}:{flow.source_port}
                </td>
                <td className="px-4 py-2.5 font-mono text-slate-300">
                  {flow.destination_ip}:{flow.destination_port}
                </td>
                <td className="px-4 py-2.5 text-slate-400">{flow.protocol}</td>
                <td className="px-4 py-2.5 font-mono text-slate-300">{flow.packet_count}</td>
                <td className="px-4 py-2.5 font-mono text-slate-300">{formatBytes(flow.byte_count)}</td>
                <td className="px-4 py-2.5 whitespace-nowrap font-mono text-xs text-slate-400">
                  {formatTimestamp(flow.start_time)}
                </td>
                <td className="px-4 py-2.5">
                  {prediction ? (
                    <div className="flex items-center gap-2">
                      <span className="text-slate-200">{prediction.attack_type}</span>
                      <SeverityBadge severity={prediction.severity} />
                    </div>
                  ) : (
                    <span className="text-slate-600">—</span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
