import { useState } from "react";
import { useAlerts } from "../hooks/useAlerts";
import { AlertsTable } from "../components/alerts/AlertsTable";
import { AlertFiltersBar } from "../components/alerts/AlertFiltersBar";
import { Pagination } from "../components/common/Pagination";
import { TableSkeleton } from "../components/common/LoadingSkeleton";
import { ErrorState } from "../components/common/ErrorState";
import { StatusDot } from "../components/common/StatusDot";
import { useWebSocketAlerts } from "../context/WebSocketContext";
import type { AlertFilters } from "../types/alert";

const DEFAULT_FILTERS: AlertFilters = { page: 1, page_size: 25, sort_by: "timestamp", sort_desc: true };

export default function Alerts() {
  const [filters, setFilters] = useState<AlertFilters>(DEFAULT_FILTERS);
  const { status } = useWebSocketAlerts();
  const query = useAlerts(filters);

  const handleSortChange = (sortBy: NonNullable<AlertFilters["sort_by"]>) => {
    setFilters((current) => ({
      ...current,
      sort_by: sortBy,
      sort_desc: current.sort_by === sortBy ? !current.sort_desc : true,
    }));
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-slate-100">Live Alerts</h1>
        <StatusDot status={status} />
      </div>

      <AlertFiltersBar filters={filters} onChange={setFilters} />

      {query.isLoading && <TableSkeleton />}
      {query.isError && <ErrorState message="Couldn't load alerts." onRetry={() => query.refetch()} />}
      {query.data && (
        <>
          <AlertsTable
            alerts={query.data.items}
            sortBy={filters.sort_by}
            sortDesc={filters.sort_desc ?? true}
            onSortChange={handleSortChange}
          />
          <Pagination
            page={query.data.page}
            pageSize={query.data.page_size}
            total={query.data.total}
            onPageChange={(page) => setFilters((current) => ({ ...current, page }))}
          />
        </>
      )}
    </div>
  );
}
