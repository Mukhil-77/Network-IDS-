interface ErrorStateProps {
  message?: string;
  onRetry?: () => void;
}

// Errors don't apologize and aren't vague - state what happened and offer
// the one action that fixes it.
export function ErrorState({ message = "Couldn't load this data.", onRetry }: ErrorStateProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-xl border border-severity-high/30 bg-severity-high/5 p-8 text-center">
      <p className="text-sm text-slate-300">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="rounded-md border border-border bg-surface-overlay px-3 py-1.5 text-sm font-medium text-slate-100 hover:border-signal/50 hover:text-signal"
        >
          Retry
        </button>
      )}
    </div>
  );
}
