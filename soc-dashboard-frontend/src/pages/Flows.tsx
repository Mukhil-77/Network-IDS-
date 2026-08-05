import { useMemo, useState } from "react";
import { useFlows } from "../hooks/useFlows";
import { useLatestAlerts } from "../hooks/useAlerts";
import { FlowsTable } from "../components/tables/FlowsTable";
import { Pagination } from "../components/common/Pagination";
import { TableSkeleton } from "../components/common/LoadingSkeleton";
import { ErrorState } from "../components/common/ErrorState";
import { SearchInput } from "../components/common/SearchInput";
import type { FlowFilters } from "../types/flow";

const DEFAULT_FILTERS: FlowFilters = { page: 1, page_size: 25 };

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
