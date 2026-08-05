interface NotAvailableCardProps {
  label: string;
  reason?: string;
}

// Used instead of fabricating numbers the backend doesn't provide (CPU,
// memory, disk, system load - Milestone 6 never implemented OS-level
// telemetry). Showing a fake number on a security dashboard is worse than
// showing nothing - this states plainly what's missing and why.
export function NotAvailableCard({ label, reason = "Requires backend telemetry (not yet implemented)" }: NotAvailableCardProps) {
  return (
    <div className="rounded-xl border border-dashed border-border bg-surface-raised/50 p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-2 font-mono text-2xl font-semibold text-slate-600">—</p>
      <p className="mt-1 text-xs text-slate-600">{reason}</p>
    </div>
  );
}
