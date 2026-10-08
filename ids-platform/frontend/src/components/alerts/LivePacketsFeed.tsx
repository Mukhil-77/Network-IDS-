import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { packetsService } from "../../services/packetsService";
import type { LivePacket } from "../../context/WebSocketContext";
import type { LiveAlertPayload } from "../../types/websocket";

const DISPLAY_LIMIT = 500;

function formatTime(iso: string): string {
  const date = new Date(iso);

  return (
    date.toLocaleTimeString([], { hour12: false }) +
    "." +
    String(date.getMilliseconds()).padStart(3, "0")
  );
}

interface LivePacketsFeedProps {
  livePackets: LivePacket[];
  liveAlerts: LiveAlertPayload[];
  /** Connection status of the /ws/alerts socket ("open" = live stream flowing). */
  socketStatus: string;
}

function getSeverityBadgeClass(severity: string): string {
  switch (severity) {
    case "Critical":
      return "bg-red-100 text-red-800 border-red-300";

    case "High":
      return "bg-orange-100 text-orange-800 border-orange-300";

    case "Medium":
      return "bg-yellow-100 text-yellow-800 border-yellow-300";

    case "Low":
      return "bg-green-100 text-green-800 border-green-300";

    default:
      return "bg-slate-100 text-slate-800 border-slate-300";
  }
}

/**
 * The "Live Packets" tab of the Alerts page.
 *
 * Displays recent packets from the backend and continuously updates
 * with packets received through the WebSocket.
 *
 * Packets belonging to flows that triggered alerts are highlighted
 * with the corresponding severity.
 */
export function LivePacketsFeed({
  livePackets,
  liveAlerts,
  socketStatus,
}: LivePacketsFeedProps) {
  const historyQuery = useQuery({
    queryKey: ["detection", "packets", "recent"],
    queryFn: () => packetsService.getRecent(DISPLAY_LIMIT),
    staleTime: 5_000,
  });

  const scrollRef = useRef<HTMLDivElement>(null);
  const [autoScroll, setAutoScroll] = useState(true);

  /*
   * Build a set of flow IDs that have triggered alerts.
   */
  const alertFlowIds = useMemo(() => {
    const flows = new Set<string>();

    liveAlerts.forEach((alert) => {
      if (alert.flow_id) {
        flows.add(alert.flow_id);
      }
    });

    return flows;
  }, [liveAlerts]);

  /*
   * Get the alert severity for a flow.
   */
  const getFlowAlertSeverity = (
    flowId: string | undefined
  ): string | null => {
    if (!flowId) {
      return null;
    }

    const alert = liveAlerts.find((a) => a.flow_id === flowId);

    return alert ? alert.severity : null;
  };

  /*
   * Merge backend history with live packets.
   * Live packets are kept first because they are newest.
   */
  const rows = useMemo<LivePacket[]>(() => {
    if (historyQuery.data?.length) {
      const known = new Set(
        livePackets.map(
          (packet) =>
            `${packet.timestamp}-${packet.src_ip}-${packet.length}-${packet.seq}`
        )
      );

      const seeded = historyQuery.data.map((packet, index) => ({
        ...packet,
        seq: -(index + 1),
      }));

      const newHistoryPackets = seeded.filter(
        (packet) =>
          !known.has(
            `${packet.timestamp}-${packet.src_ip}-${packet.length}-${packet.seq}`
          )
      );

      return [...livePackets, ...newHistoryPackets].slice(
        0,
        DISPLAY_LIMIT
      );
    }

    return livePackets.slice(0, DISPLAY_LIMIT);
  }, [historyQuery.data, livePackets]);

  const isLive = socketStatus === "open";

  const totalSeen =
    rows.length > 0
      ? Math.max(livePackets[0]?.seq ?? 0, rows.length)
      : rows.length;

  /*
   * Keep the view pinned to the newest packet when auto-scroll is enabled.
   */
  useEffect(() => {
    if (autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = 0;
    }
  }, [rows, autoScroll]);

  return (
    <div className="rounded-xl border border-border bg-surface-raised">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <div className="flex items-center gap-2">
          <span
            className={`h-2 w-2 rounded-full ${
              isLive
                ? "animate-pulse-live bg-emerald-400"
                : "bg-slate-500"
            }`}
          />

          <h2 className="text-sm font-medium text-slate-200">
            Live Packet Stream
          </h2>
        </div>

        <div className="flex items-center gap-4 text-xs text-slate-400">
          <label className="flex cursor-pointer select-none items-center gap-1.5">
            <input
              type="checkbox"
              checked={autoScroll}
              onChange={(e) => setAutoScroll(e.target.checked)}
              className="accent-blue-500"
            />

            Auto-scroll
          </label>

          <span>{isLive ? "streaming" : "socket closed"}</span>

          <span className="font-mono">
            {totalSeen} packets
          </span>
        </div>
      </div>

      {/* Packet list */}
      <div
        ref={scrollRef}
        className="max-h-[420px] overflow-auto"
      >
        {rows.length === 0 ? (
          <div className="px-4 py-10 text-center text-sm text-slate-500">
            <p className="font-medium text-slate-400">
              No packets yet
            </p>

            <p className="mt-1">
              Start the detection pipeline (
              <span className="font-mono">
                POST /detection/start
              </span>
              ) to begin capturing. Packets stream here in real
              time as they are parsed.
            </p>
          </div>
        ) : (
          <table className="w-full text-left text-sm">
            <thead className="sticky top-0 bg-surface-raised text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-2 font-medium">
                  Time
                </th>

                <th className="px-4 py-2 font-medium">
                  Source
                </th>

                <th className="px-4 py-2 font-medium">
                  Destination
                </th>

                <th className="px-4 py-2 font-medium">
                  Proto
                </th>

                <th className="px-4 py-2 text-right font-medium">
                  Len
                </th>

                <th className="px-4 py-2 font-medium">
                  Flags
                </th>

                <th className="px-4 py-2 font-medium">
                  Detection
                </th>
              </tr>
            </thead>

            <tbody className="divide-y divide-border">
              {rows.map((packet) => {
                const isAlertFlow = packet.flow_id
                  ? alertFlowIds.has(packet.flow_id)
                  : false;

                const alertSeverity = isAlertFlow
                  ? getFlowAlertSeverity(packet.flow_id)
                  : null;

                return (
                  <tr
                    key={`${packet.seq}-${packet.timestamp}`}
                    className={`font-mono text-xs text-slate-300 ${
                      isAlertFlow
                        ? "bg-red-500/10 hover:bg-surface-overlay"
                        : "hover:bg-surface-overlay"
                    }`}
                  >
                    {/* Time */}
                    <td className="whitespace-nowrap px-4 py-1.5">
                      {formatTime(packet.timestamp)}
                    </td>

                    {/* Source */}
                    <td className="whitespace-nowrap px-4 py-1.5">
                      {packet.src_ip}

                      <span className="text-slate-500">
                        :{packet.src_port}
                      </span>
                    </td>

                    {/* Destination */}
                    <td className="whitespace-nowrap px-4 py-1.5">
                      {packet.dst_ip}

                      <span className="text-slate-500">
                        :{packet.dst_port}
                      </span>
                    </td>

                    {/* Protocol */}
                    <td className="px-4 py-1.5">
                      <span
                        className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${
                          packet.protocol === "TCP"
                            ? "bg-sky-500/15 text-sky-400"
                            : "bg-amber-500/15 text-amber-400"
                        }`}
                      >
                        {packet.protocol}
                      </span>
                    </td>

                    {/* Length */}
                    <td className="px-4 py-1.5 text-right">
                      {packet.length}
                    </td>

                    {/* Flags */}
                    <td className="px-4 py-1.5 text-slate-400">
                      {packet.flags?.join("") || "—"}
                    </td>

                    {/* Detection */}
                    <td className="px-4 py-1.5">
                      {isAlertFlow && (
                        <span
                          className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-semibold ${getSeverityBadgeClass(
                            alertSeverity || "Low"
                          )}`}
                        >
                          {alertSeverity || "Low"}
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}