import { createContext, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { AlertSocket } from "../services/websocketService";
import { useAuth } from "./AuthContext";
import type { ConnectionStatus } from "../types/common";
import type { WSEvent } from "../types/websocket";
import type { LiveAlertPayload, LivePacketPayload } from "../types/websocket";
import type { AlertRow, PaginatedAlerts } from "../types/alert";

const MAX_LIVE_ALERTS = 200;
const MAX_LIVE_PACKETS = 200;
const RESPONSE_EVENT_TYPES = new Set(["response_started", "response_completed", "response_failed", "rollback_completed"]);

// A packet as the Live Packets feed renders it: the WS payload plus a
// client-assigned sequence number (the backend sends no id for packets).
export interface LivePacket extends LivePacketPayload {
  seq: number;
}

interface WebSocketContextValue {
  status: ConnectionStatus;
  liveAlerts: AlertRow[];
  livePackets: LivePacket[];
}

const WebSocketContext = createContext<WebSocketContextValue | null>(null);

function toAlertRow(payload: LiveAlertPayload): AlertRow {
  // Map severity string to Severity type
  const severityMap: Record<string, "Critical" | "High" | "Medium" | "Low" | "Legitimate" | "Unknown"> = {
    "Critical": "Critical",
    "High": "High",
    "Medium": "Medium",
    "Low": "Low",
    "Legitimate": "Legitimate",
    "Unknown": "Unknown",
  };
  
  const severity = severityMap[payload.severity] || "Medium";
  
  // Map severity to risk level
  const severityToRiskLevel: Record<string, "LOW" | "GUARDED" | "MEDIUM" | "HIGH" | "CRITICAL"> = {
    "Critical": "CRITICAL",
    "High": "HIGH",
    "Medium": "MEDIUM",
    "Low": "LOW",
    "Legitimate": "LOW",
    "Unknown": "MEDIUM",
  };
  
  // Simple threat tag inference based on severity and attack type
  let threatTag: "Known Malicious" | "Suspicious" | "Unknown" | "Trusted" = "Unknown";
  if (payload.severity === "Critical" || payload.severity === "High") {
    threatTag = "Known Malicious";
  } else if (payload.severity === "Medium") {
    threatTag = "Suspicious";
  } else if (payload.severity === "Low") {
    threatTag = "Trusted";
  }
  
  return {
    id: payload.id,
    timestamp: payload.timestamp,
    attack_type: payload.attack,
    confidence: payload.confidence,
    severity: severity,
    risk_score: Math.round(payload.confidence),
    risk_level: severityToRiskLevel[payload.severity] || "MEDIUM",
    source_ip: payload.source_ip,
    destination_ip: payload.destination_ip,
    protocol: payload.protocol,
    flow_id: payload.flow_id,
    model_version: payload.model_version,
    status: "new",
    threat_tag: threatTag,
    priority: payload.severity === "Critical" ? "P1_CRITICAL" : 
              payload.severity === "High" ? "P2_HIGH" :
              payload.severity === "Medium" ? "P3_MEDIUM" : "P4_LOW",
    priority_score: payload.confidence,
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
  const [livePackets, setLivePackets] = useState<LivePacket[]>([]);
  const socketRef = useRef<AlertSocket | null>(null);
  const packetSeqRef = useRef(0);
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
      if (event.type === "packet") {
        packetSeqRef.current += 1;
        setLivePackets((current) =>
          [{ ...(event.payload as LivePacketPayload), seq: packetSeqRef.current }, ...current].slice(0, MAX_LIVE_PACKETS),
        );
        return;
      }

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

  const value = useMemo(() => ({ status, liveAlerts, livePackets }), [status, liveAlerts, livePackets]);

  return <WebSocketContext.Provider value={value}>{children}</WebSocketContext.Provider>;
}

export function useWebSocketAlerts(): WebSocketContextValue {
  const ctx = useContext(WebSocketContext);
  if (!ctx) throw new Error("useWebSocketAlerts must be used within a WebSocketProvider");
  return ctx;
}
