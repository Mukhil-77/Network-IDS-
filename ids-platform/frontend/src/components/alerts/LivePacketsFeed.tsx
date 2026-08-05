import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { packetsService } from "../../services/packetsService";
import type { LivePacket } from "../../context/WebSocketContext";

const DISPLAY_LIMIT = 100;

function formatTime(iso: string): string {
  const date = new Date(iso);
  return date.toLocaleTimeString([], { hour12: false }) + "." + String(date.getMilliseconds()).padStart(3, "0");
}

interface LivePacketsFeedProps {
  livePackets: LivePacket[];
  /** Connection status of the /ws/alerts socket ("open" = live stream flowing). */
  socketStatus: string;
}

/**
 * The "Live Packets" tab of the Alerts page: an in-memory, newest-first feed
 * of every packet the detection pipeline has parsed. Seeded from the
 * backend's recent-packet buffer (GET /detection/packets/recent), then kept
 * current by the WebSocket "packet" events fanned out through
 * WebSocketContext.livePackets.
 */
export function LivePacketsFeed({ livePackets, socketStatus }: LivePacketsFeedProps) {
  const historyQuery = useQuery({
    queryKey: ["detection", "packets", "recent"],
    queryFn: () => packetsService.getRecent(DISPLAY_LIMIT),
    staleTime: 5_000,
  });

  const rows = useMemo<LivePacket[]>(() => {
    if (historyQuery.data?.length) {
      const known = new Set(livePackets.map((packet) => `${packet.timestamp}-${packet.src_ip}-${packet.length}-${packet.seq}`));
      const seeded = historyQuery.data.map((packet, index) => ({ ...packet, seq: -(index + 1) }));
      return [...livePackets, ...seeded.filter((packet) => !known.has(`${packet.timestamp}-${packet.src_ip}-${packet.length}-${packet.seq}`))].slice(0, DISPLAY_LIMIT);
    }
    return livePackets.slice(0, DISPLAY_LIMIT);
  }, [historyQuery.data, livePackets]);

  const isLive = socketStatus === "open";
  const totalSeen = rows.length > 0 ? Math.max(livePackets[0]?.seq ?? 0, rows.length) : rows.length;

  return (
    <div className="rounded-xl border border-border bg-surface-raised">
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <div className="flex items-center gap-2">
          <span className={`h-2 w-2 rounded-full ${isLive ? "animate-pulse-live bg-emerald-400" : "bg-slate-500"}`} />
          <h2 className="text-sm font-medium text-slate-200">Live Packet Stream</h2>
        </div>
        <div className="flex items-center gap-4 text-xs text-slate-400">
          <span>{isLive ? "streaming" : "socket closed"}</span>
          <span className="font-mono">{totalSeen} packets</span>
        </div>
      </div>

      <div className="max-h-[420px] overflow-auto">
        {rows.length === 0 ? (
          <div className="px-4 py-10 text-center text-sm text-slate-500">
            <p className="font-medium text-slate-400">No packets yet</p>
            <p className="mt-1">
              Start the detection pipeline (<span className="font-mono">POST /detection/start</span>) to begin
              capturing - packets stream here in real time as they are parsed.
            </p>
          </div>
        ) : (
          <table className="w-full text-left text-sm">
            <thead className="sticky top-0 bg-surface-raised text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-2 font-medium">Time</th>
                <th className="px-4 py-2 font-medium">Source</th>
                <th className="px-4 py-2 font-medium">Destination</th>
                <th className="px-4 py-2 font-medium">Proto</th>
                <th className="px-4 py-2 font-medium text-right">Len</th>
                <th className="px-4 py-2 font-medium">Flags</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {rows.map((packet) => (
                <tr key={packet.seq} className="font-mono text-xs text-slate-300 hover:bg-surface-overlay">
                  <td className="whitespace-nowrap px-4 py-1.5">{formatTime(packet.timestamp)}</td>
                  <td className="whitespace-nowrap px-4 py-1.5">
                    {packet.src_ip}
                    <span className="text-slate-500">:{packet.src_port}</span>
                  </td>
                  <td className="whitespace-nowrap px-4 py-1.5">
                    {packet.dst_ip}
                    <span className="text-slate-500">:{packet.dst_port}</span>
                  </td>
                  <td className="px-4 py-1.5">
                    <span className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${
                      packet.protocol === "TCP" ? "bg-sky-500/15 text-sky-400" : "bg-amber-500/15 text-amber-400"
                    }`}>
                      {packet.protocol}
                    </span>
                  </td>
                  <td className="px-4 py-1.5 text-right">{packet.length}</td>
                  <td className="px-4 py-1.5 text-slate-400">{packet.flags.join("") || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
