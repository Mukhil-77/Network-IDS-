import type { ConnectionStatus } from "../../types/common";

const STATUS_CONFIG: Record<ConnectionStatus, { color: string; label: string; pulse: boolean }> = {
  open: { color: "bg-signal", label: "Live", pulse: true },
  connecting: { color: "bg-severity-medium", label: "Connecting…", pulse: true },
  closed: { color: "bg-slate-500", label: "Disconnected", pulse: false },
  error: { color: "bg-severity-critical", label: "Connection error", pulse: false },
};

// The one signature element of this design (per frontend-design guidance):
// a radar-style live pulse tied directly to the actual WebSocket state, not
// decorative - it genuinely reflects whether alerts are streaming right now.
export function StatusDot({ status }: { status: ConnectionStatus }) {
  const config = STATUS_CONFIG[status];
  return (
    <div className="flex items-center gap-2">
      <span className="relative flex h-2.5 w-2.5">
        {config.pulse && (
          <span className={`absolute inline-flex h-full w-full animate-pulse-live rounded-full ${config.color} opacity-60`} />
        )}
        <span className={`relative inline-flex h-2.5 w-2.5 rounded-full ${config.color}`} />
      </span>
      <span className="text-xs font-medium text-slate-400">{config.label}</span>
    </div>
  );
}
