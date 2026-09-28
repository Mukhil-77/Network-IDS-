import { useState, useMemo } from "react";
import { useAlerts } from "../hooks/useAlerts";
import { AlertsTable } from "../components/alerts/AlertsTable";
import { AlertFiltersBar } from "../components/alerts/AlertFiltersBar";
import { LivePacketsFeed } from "../components/alerts/LivePacketsFeed";
import { Pagination } from "../components/common/Pagination";
import { TableSkeleton } from "../components/common/LoadingSkeleton";
import { ErrorState } from "../components/common/ErrorState";
import { StatusDot } from "../components/common/StatusDot";
import { useWebSocketAlerts } from "../context/WebSocketContext";
import type { AlertFilters } from "../types/alert";
import type { LiveAlertPayload } from "../types/websocket";
import type { AlertRow } from "../types/alert";

const DEFAULT_FILTERS: AlertFilters = { page: 1, page_size: 25, sort_by: "timestamp", sort_desc: true };

const TAB_CLASSES = {
  active: "border-emerald-400 text-emerald-300",
  idle: "border-transparent text-slate-400 hover:text-slate-200",
};

/**
 * Convert AlertRow (from WebSocketContext) to LiveAlertPayload (for LivePacketsFeed)
 * since LivePacketsFeed expects LiveAlertPayload[] with attack, source_port, destination_port fields
 */
function toLiveAlertPayload(alert: AlertRow): LiveAlertPayload {
  return {
    id: alert.id,
    timestamp: alert.timestamp,
    attack: alert.attack_type,
    severity: alert.severity,
    confidence: alert.confidence,
    source_ip: alert.source_ip,
    destination_ip: alert.destination_ip,
    protocol: alert.protocol,
    flow_id: alert.flow_id,
    source_port: 0, // Not available in AlertRow, default to 0
    destination_port: 0, // Not available in AlertRow, default to 0
    model_version: alert.model_version,
  };
}

export default function Alerts() {
  const [filters, setFilters] = useState<AlertFilters>(DEFAULT_FILTERS);
  const [tab, setTab] = useState<"alerts" | "packets">("alerts");
  const { status, livePackets, liveAlerts } = useWebSocketAlerts();
  const query = useAlerts(filters);

  // Convert AlertRow[] to LiveAlertPayload[] for LivePacketsFeed
  const liveAlertsForPackets = useMemo(
    () => liveAlerts.map(toLiveAlertPayload),
    [liveAlerts]
  );

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

      <div className="flex items-center gap-1 border-b border-border text-sm">
        <button
          type="button"
          onClick={() => setTab("alerts")}
          className={`border-b-2 px-3 py-2 font-medium transition-colors ${tab === "alerts" ? TAB_CLASSES.active : TAB_CLASSES.idle}`}
        >
          Alerts
        </button>
        <button
          type="button"
          onClick={() => setTab("packets")}
          className={`border-b-2 px-3 py-2 font-medium transition-colors ${tab === "packets" ? TAB_CLASSES.active : TAB_CLASSES.idle}`}
        >
          Live Packets
        </button>
      </div>

      {tab === "packets" ? (
        <LivePacketsFeed livePackets={livePackets} liveAlerts={liveAlertsForPackets} socketStatus={status} />
      ) : (
        <>
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
        </>
      )}
    </div>
  );
}
