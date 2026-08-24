import { createContext, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { AlertSocket } from "../services/websocketService";
import { useAuth } from "./AuthContext";
import type { ConnectionStatus } from "../types/common";
import type { WSEvent } from "../types/websocket";
import type { LiveAlertPayload } from "../types/websocket";
import type { AlertRow, PaginatedAlerts } from "../types/alert";

const MAX_LIVE_ALERTS = 200;
const RESPONSE_EVENT_TYPES = new Set(["response_started", "response_completed", "response_failed", "rollback_completed"]);

interface WebSocketContextValue {
  status: ConnectionStatus;
  liveAlerts: AlertRow[];
}

const WebSocketContext = createContext<WebSocketContextValue | null>(null);

function toAlertRow(payload: LiveAlertPayload): AlertRow {
  return {
    id: payload.id,
    timestamp: payload.timestamp,
    attack_type: payload.attack,
    confidence: payload.confidence,
    severity: payload.severity,
    source_ip: payload.source_ip,
    destination_ip: payload.destination_ip,
    protocol: payload.protocol,
    flow_id: payload.flow_id,
    model_version: payload.model_version,
    // Not present on the live WS payload (see types/websocket.ts's
    // docstring) - "new" matches the default AlertService persists with.
    status: "new",
  };
}

/**
 * Owns the single AlertSocket connection for the whole app and fans its
 * events out two ways:
 *   1. `liveAlerts` - a bounded in-memory feed any component can read via
 *      useWebSocketAlerts(), for immediate rendering (e.g. the live pulse
 *      on the Alerts page).
 *   2. Directly into the React Query cache for the alerts/responses/statistics
 *      queries, so REST-backed views update the instant something happens -
 *      no polling, no manual refetch.
 *
 * Milestone 8: response_started/completed/failed/rollback_completed events
 * (backend/response_engine/response_service.py) arrive on this same socket -
 * they invalidate the responses list/history queries and the affected
 * alert's cached status, rather than getting their own connection.
 */
export function WebSocketProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<ConnectionStatus>("closed");
  const [liveAlerts, setLiveAlerts] = useState<AlertRow[]>([]);
  const socketRef = useRef<AlertSocket | null>(null);
  const queryClient = useQueryClient();
  const { user } = useAuth();

  useEffect(() => {
    if (!user) {
      // Logged out (or never logged in, or session expired) - make sure
      // any existing connection is torn down; nothing to connect yet.
      socketRef.current?.disconnect();
      socketRef.current = null;
      setStatus("closed");
      return;
    }

    const socket = new AlertSocket();
    socketRef.current = socket;

    const unsubscribeStatus = socket.onStatusChange(setStatus);
    const unsubscribeMessages = socket.onAlert((event: WSEvent) => {
      if (event.type === "alert") {
        const row = toAlertRow(event.payload as LiveAlertPayload);
        setLiveAlerts((current) => [row, ...current].slice(0, MAX_LIVE_ALERTS));

        // Prepend into any cached "first page, default filters" alerts query
        // so the Alerts table updates instantly without a network round trip.
        queryClient.setQueriesData<PaginatedAlerts>({ queryKey: ["alerts"] }, (existing) => {
          if (!existing) return existing;
          return { ...existing, items: [row, ...existing.items], total: existing.total + 1 };
        });

        // Statistics derive from alert counts/breakdowns server-side - rather
        // than reimplementing that aggregation client-side, just invalidate
        // so the next render refetches. Still event-driven, not polling.
        queryClient.invalidateQueries({ queryKey: ["statistics"] });
        return;
      }

      if (RESPONSE_EVENT_TYPES.has(event.type)) {
        queryClient.invalidateQueries({ queryKey: ["responses"] });
        // A completed/failed response changes the parent alert's status
        // (see response_service.py's _update_alert_status) - invalidate
        // rather than trying to patch the cache in place, since we don't
        // know which cached alert page (if any) currently holds that row.
        queryClient.invalidateQueries({ queryKey: ["alerts"] });
      }
    });

    socket.connect();

    return () => {
      unsubscribeStatus();
      unsubscribeMessages();
      socket.disconnect();
    };
  }, [queryClient, user]);

  const value = useMemo(() => ({ status, liveAlerts }), [status, liveAlerts]);

  return <WebSocketContext.Provider value={value}>{children}</WebSocketContext.Provider>;
}

export function useWebSocketAlerts(): WebSocketContextValue {
  const ctx = useContext(WebSocketContext);
  if (!ctx) throw new Error("useWebSocketAlerts must be used within a WebSocketProvider");
  return ctx;
}
