import { useMemo, useState } from "react";
import { useFlows, useFlowSummary } from "../hooks/useFlows";
import { useLatestAlerts } from "../hooks/useAlerts";
import { FlowsTable } from "../components/tables/FlowsTable";
import { Pagination } from "../components/common/Pagination";
import { TableSkeleton, CardSkeleton } from "../components/common/LoadingSkeleton";
import { ErrorState } from "../components/common/ErrorState";
import { SearchInput } from "../components/common/SearchInput";
import type { FlowFilters } from "../types/flow";

const DEFAULT_FILTERS: FlowFilters = { page: 1, page_size: 25 };

function formatBytes(bytes: number): string {
  if (bytes >= 1_048_576) return `${(bytes / 1_048_576).toFixed(1)} MB`;
  if (bytes >= 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${bytes} B`;
}

function FlowSummaryCards() {
  const summaryQuery = useFlowSummary();
  const summary = summaryQuery.data;

  if (summaryQuery.isLoading) {
    return (
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => <CardSkeleton key={i} />)}
      </div>
    );
  }
  if (!summary) return null;

  const protocolBuckets = Object.entries(summary.per_protocol).sort((a, b) => b[1].flows - a[1].flows);

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <div className="rounded-xl border border-border bg-surface-raised p-4">
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Total Flows</p>
          <p className="mt-2 font-mono text-2xl font-semibold text-slate-100">{summary.total_flows}</p>
        </div>
        <div className="rounded-xl border border-border bg-surface-raised p-4">
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Packets</p>
          <p className="mt-2 font-mono text-2xl font-semibold text-slate-100">{summary.total_packets}</p>
        </div>
        <div className="rounded-xl border border-border bg-surface-raised p-4">
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Bytes</p>
          <p className="mt-2 font-mono text-2xl font-semibold text-slate-100">{formatBytes(summary.total_bytes)}</p>
        </div>
        <div className="rounded-xl border border-border bg-surface-raised p-4">
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Protocols</p>
          <p className="mt-2 font-mono text-2xl font-semibold text-slate-100">{protocolBuckets.length || "—"}</p>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="rounded-xl border border-border bg-surface-raised p-4">
          <h2 className="mb-3 text-sm font-medium text-slate-300">Flows by Protocol</h2>
          {protocolBuckets.length === 0 ? (
            <p className="text-sm text-slate-500">No flow data captured yet.</p>
          ) : (
            <div className="space-y-2">
              {protocolBuckets.map(([protocol, bucket]) => (
                <div key={protocol} className="flex items-center gap-3 text-sm">
                  <span className="w-14 font-mono text-slate-200">{protocol}</span>
                  <div className="h-2 flex-1 rounded-full bg-gray-800">
                    <div
                      className="h-2 rounded-full bg-signal"
                      style={{ width: `${(bucket.flows / summary.total_flows) * 100}%` }}
                    />
                  </div>
                  <span className="font-mono text-xs text-slate-400">
                    {bucket.flows} flows · {formatBytes(bucket.bytes)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="rounded-xl border border-border bg-surface-raised p-4">
          <h2 className="mb-3 text-sm font-medium text-slate-300">Top Talkers</h2>
          {summary.top_talkers.length === 0 ? (
            <p className="text-sm text-slate-500">No flow data captured yet.</p>
          ) : (
            <div className="space-y-2">
              {summary.top_talkers.map((talker, index) => (
                <div key={talker.source_ip} className="flex items-center gap-3 text-sm">
                  <span className="w-5 text-right font-mono text-xs text-slate-500">{index + 1}</span>
                  <span className="flex-1 truncate font-mono text-slate-200">{talker.source_ip}</span>
                  <span className="text-xs text-slate-400">{talker.flows} flows</span>
                  <span className="w-20 text-right font-mono text-xs text-slate-400">{formatBytes(talker.bytes)}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function Flows() {
  const [filters, setFilters] = useState<FlowFilters>(DEFAULT_FILTERS);
  const flowsQuery = useFlows(filters);
  // Best-effort join for the "Prediction" column - see FlowsTable's docstring.
  const alertsQuery = useLatestAlerts(200);

  const predictionByFlowId = useMemo(() => {
    const map = new Map<string, { attack_type: string; severity: string }>();
    alertsQuery.data?.forEach((alert) => map.set(alert.flow_id, { attack_type: alert.attack_type, severity: alert.severity }));
    return map;
  }, [alertsQuery.data]);

  return (
    <div className="space-y-4">
      <h1 className="text-lg font-semibold text-slate-100">Network Flows</h1>

      <FlowSummaryCards />

      <div className="flex flex-wrap gap-3 rounded-xl border border-border bg-surface-raised p-3">
        <div className="w-48">
          <SearchInput
            value={filters.source_ip ?? ""}
            onChange={(v) => setFilters((c) => ({ ...c, source_ip: v || undefined, page: 1 }))}
            placeholder="Source IP…"
          />
        </div>
        <div className="w-48">
          <SearchInput
            value={filters.destination_ip ?? ""}
            onChange={(v) => setFilters((c) => ({ ...c, destination_ip: v || undefined, page: 1 }))}
            placeholder="Destination IP…"
          />
        </div>
        <select
          value={filters.protocol ?? ""}
          onChange={(e) => setFilters((c) => ({ ...c, protocol: e.target.value || undefined, page: 1 }))}
          className="rounded-md border border-border bg-surface-raised px-3 py-1.5 text-sm text-slate-100 focus:border-signal focus:outline-none"
        >
          <option value="">All protocols</option>
          <option value="TCP">TCP</option>
          <option value="UDP">UDP</option>
          <option value="ICMP">ICMP</option>
        </select>
      </div>

      {flowsQuery.isLoading && <TableSkeleton />}
      {flowsQuery.isError && <ErrorState message="Couldn't load flows." onRetry={() => flowsQuery.refetch()} />}
      {flowsQuery.data && (
        <>
          <FlowsTable flows={flowsQuery.data.items} predictionByFlowId={predictionByFlowId} />
          <Pagination
            page={flowsQuery.data.page}
            pageSize={flowsQuery.data.page_size}
            total={flowsQuery.data.total}
            onPageChange={(page) => setFilters((c) => ({ ...c, page }))}
          />
        </>
      )}
    </div>
  );
}