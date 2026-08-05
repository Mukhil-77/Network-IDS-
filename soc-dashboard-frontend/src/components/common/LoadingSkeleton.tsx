export function TableSkeleton({ rows = 8, columns = 6 }: { rows?: number; columns?: number }) {
  return (
    <div className="animate-pulse space-y-2" role="status" aria-label="Loading data">
      {Array.from({ length: rows }).map((_, rowIndex) => (
        <div key={rowIndex} className="flex gap-4">
          {Array.from({ length: columns }).map((__, colIndex) => (
            <div key={colIndex} className="h-4 flex-1 rounded bg-surface-overlay" />
          ))}
        </div>
      ))}
    </div>
  );
}

export function CardSkeleton() {
  return (
    <div className="animate-pulse rounded-xl border border-border bg-surface-raised p-4" role="status" aria-label="Loading">
      <div className="h-3 w-24 rounded bg-surface-overlay" />
      <div className="mt-3 h-7 w-16 rounded bg-surface-overlay" />
    </div>
  );
}

export function ChartSkeleton() {
  return (
    <div
      className="flex h-64 animate-pulse items-end gap-2 rounded-xl border border-border bg-surface-raised p-4"
      role="status"
      aria-label="Loading chart"
    >
      {Array.from({ length: 12 }).map((_, i) => (
        <div key={i} className="flex-1 rounded bg-surface-overlay" style={{ height: `${20 + ((i * 37) % 70)}%` }} />
      ))}
    </div>
  );
}
