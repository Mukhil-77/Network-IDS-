import { severityBadgeClasses } from "../../utils/severity";

export function SeverityBadge({ severity }: { severity: string }) {
  return (
    <span
      className={`inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium font-mono ${severityBadgeClasses(
        severity
      )}`}
    >
      {severity}
    </span>
  );
}

export function StatusBadge({ status }: { status: string }) {
  const isNew = status === "new";
  return (
    <span
      className={`inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium ${
        isNew
          ? "bg-signal/15 text-signal border-signal/30"
          : "bg-slate-500/15 text-slate-300 border-slate-500/30"
      }`}
    >
      {status}
    </span>
  );
}
