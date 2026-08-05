import type { ReactNode } from "react";
import { SystemGauge } from "./SystemGauge";
import { Sparkline } from "./Sparkline";
import type { SeriesPoint } from "./useTelemetrySeries";

export function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return "0 B";
  if (bytes === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.min(units.length - 1, Math.floor(Math.log(bytes) / Math.log(1024)));
  const value = bytes / 1024 ** i;
  return `${value.toFixed(value >= 100 || i === 0 ? 0 : 1)} ${units[i]}`;
}

interface TelemetryCardProps {
  title: string;
  percent: number | null;
  color: string;
  detail?: string;
  footer?: string;
  series: SeriesPoint[];
  badge?: ReactNode;
}

/**
 * One task-manager tile: title, circular gauge, textual detail and a rolling
 * history sparkline fed by the /system/stats poll.
 */
export function TelemetryCard({ title, percent, color, detail, footer, series, badge }: TelemetryCardProps) {
  return (
    <div className="flex flex-col rounded-xl border border-border bg-surface-raised p-4">
      <div className="flex items-start justify-between">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-medium text-slate-300">{title}</h3>
            {badge}
          </div>
          {detail && <p className="mt-1 text-xs text-slate-500">{detail}</p>}
        </div>
        {percent !== null && <SystemGauge percent={percent} color={color} label={`${title} ${percent.toFixed(0)}%`} />}
      </div>
      {footer && <p className="mt-2 font-mono text-xs text-slate-400">{footer}</p>}
      <div className="mt-2">
        <Sparkline series={series} color={color} />
      </div>
    </div>
  );
}
