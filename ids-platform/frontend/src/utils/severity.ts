import type { Severity } from "../types/alert";

// Single source of truth for severity -> color, so a table badge and a
// chart legend can never silently drift apart.
const SEVERITY_COLORS: Record<string, string> = {
  Critical: "#f43f5e",
  High: "#f97316",
  Medium: "#eab308",
  Low: "#38bdf8",
  BENIGN: "#34d399",
};

export function severityColor(severity: string): string {
  return SEVERITY_COLORS[severity] ?? "#94a3b8"; // neutral slate for an unrecognized value
}

export function severityBadgeClasses(severity: string): string {
  switch (severity) {
    case "Critical":
      return "bg-severity-critical/15 text-severity-critical border-severity-critical/30";
    case "High":
      return "bg-severity-high/15 text-severity-high border-severity-high/30";
    case "Medium":
      return "bg-severity-medium/15 text-severity-medium border-severity-medium/30";
    case "Low":
      return "bg-severity-low/15 text-severity-low border-severity-low/30";
    default:
      return "bg-slate-500/15 text-slate-300 border-slate-500/30";
  }
}

export const SEVERITY_ORDER: Severity[] = ["Critical", "High", "Medium", "Low"];
