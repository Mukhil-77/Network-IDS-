import { Area, AreaChart, ResponsiveContainer } from "recharts";
import type { SeriesPoint } from "./useTelemetrySeries";

interface SparklineProps {
  series: SeriesPoint[];
  color: string;
  height?: number;
}

/**
 * Tiny no-axis area chart for the rolling history behind each task-manager
 * gauge. Recharts, same as the analytics charts (see charts/).
 */
export function Sparkline({ series, color, height = 36 }: SparklineProps) {
  const gradientId = `spark-${color.replace("#", "")}`;

  if (series.length < 2) return <div style={{ height }} aria-hidden />;

  return (
    <div aria-hidden>
      <ResponsiveContainer width="100%" height={height}>
        <AreaChart data={series} margin={{ top: 2, right: 0, bottom: 0, left: 0 }}>
          <defs>
            <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.3} />
              <stop offset="100%" stopColor={color} stopOpacity={0} />
            </linearGradient>
          </defs>
          <Area
            type="monotone"
            dataKey="v"
            stroke={color}
            strokeWidth={1.5}
            fill={`url(#${gradientId})`}
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
