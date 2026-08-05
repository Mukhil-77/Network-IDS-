import { useState } from "react";

import { useResponses, useRollbackResponse } from "../hooks/useResponses";
import { ResponseHistoryTable } from "../components/responses/ResponseHistoryTable";
import { Pagination } from "../components/common/Pagination";
import { TableSkeleton } from "../components/common/LoadingSkeleton";
import { ErrorState } from "../components/common/ErrorState";
import { SearchInput } from "../components/common/SearchInput";
import type { ResponseFilters } from "../types/response";

const DEFAULT_FILTERS: ResponseFilters = { page: 1, page_size: 25 };

export default function ResponseHistoryPage() {
  const [filters, setFilters] = useState<ResponseFilters>(DEFAULT_FILTERS);
  const query = useResponses(filters);
  const rollbackMutation = useRollbackResponse();

  return (
    <div className="space-y-4">
      <h1 className="text-lg font-semibold text-slate-100">Response History</h1>

      <div className="flex flex-wrap gap-3 rounded-xl border border-border bg-surface-raised p-3">
        <div className="w-48">
          <SearchInput
            value={filters.alert_id ?? ""}
            onChange={(v) => setFilters((c) => ({ ...c, alert_id: v || undefined, page: 1 }))}
            placeholder="Alert ID…"
          />
        </div>
        <div className="w-40">
          <SearchInput
            value={filters.action ?? ""}
            onChange={(v) => setFilters((c) => ({ ...c, action: v || undefined, page: 1 }))}
            placeholder="Action…"
          />
        </div>
        <select
          value={filters.status ?? ""}
          onChange={(e) => setFilters((c) => ({ ...c, status: e.target.value || undefined, page: 1 }))}
          className="rounded-md border border-border bg-surface-raised px-3 py-1.5 text-sm text-slate-100 focus:border-signal focus:outline-none"
        >
          <option value="">All statuses</option>
          <option value="success">success</option>
          <option value="failed">failed</option>
          <option value="skipped">skipped</option>
        </select>
        <select
          value={filters.mode ?? ""}
          onChange={(e) => setFilters((c) => ({ ...c, mode: e.target.value || undefined, page: 1 }))}
          className="rounded-md border border-border bg-surface-raised px-3 py-1.5 text-sm text-slate-100 focus:border-signal focus:outline-none"
        >
          <option value="">All modes</option>
          <option value="simulation">simulation</option>
          <option value="live">live</option>
        </select>
      </div>

      {query.isLoading && <TableSkeleton />}
      {query.isError && <ErrorState message="Couldn't load response history." onRetry={() => query.refetch()} />}
      {query.data && (
        <>
          <ResponseHistoryTable
            responses={query.data.items}
            onRollback={(id) => rollbackMutation.mutate(id)}
            rollingBackId={rollbackMutation.isPending ? rollbackMutation.variables : undefined}
          />
          <Pagination
            page={query.data.page}
            pageSize={query.data.page_size}
            total={query.data.total}
            onPageChange={(page) => setFilters((c) => ({ ...c, page }))}
          />
        </>
      )}
    </div>
  );
}
