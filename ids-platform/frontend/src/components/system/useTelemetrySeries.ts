import { useEffect, useRef, useState } from "react";

export interface SeriesPoint {
  t: number;
  v: number;
}

/**
 * Appends `value` to a capped time series whenever it changes, so the
 * task-manager cards can draw rolling history sparklines from the 2 s
 * /system/stats poll. One instance per metric.
 */
export function useTelemetrySeries(value: number | undefined, maxPoints = 60): SeriesPoint[] {
  const [series, setSeries] = useState<SeriesPoint[]>([]);
  const lastAppendedRef = useRef(0);

  useEffect(() => {
    if (value === undefined) return;
    const now = Date.now();
    if (now - lastAppendedRef.current < 500) return;
    lastAppendedRef.current = now;
    setSeries((current) => {
      const next = [...current, { t: now, v: value }];
      return next.length > maxPoints ? next.slice(next.length - maxPoints) : next;
    });
  }, [value, maxPoints]);

  return series;
}
