interface PaginationProps {
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
}

export function Pagination({ page, pageSize, total, onPageChange }: PaginationProps) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div className="flex items-center justify-between border-t border-border px-1 py-3 text-sm text-slate-400">
      <span>
        Page <span className="font-mono text-slate-200">{page}</span> of{" "}
        <span className="font-mono text-slate-200">{totalPages}</span> · {total} total
      </span>
      <div className="flex gap-2">
        <button
          disabled={page <= 1}
          onClick={() => onPageChange(page - 1)}
          className="rounded-md border border-border px-2.5 py-1 disabled:opacity-40 hover:border-signal/50 hover:text-signal disabled:hover:border-border disabled:hover:text-slate-400"
        >
          Previous
        </button>
        <button
          disabled={page >= totalPages}
          onClick={() => onPageChange(page + 1)}
          className="rounded-md border border-border px-2.5 py-1 disabled:opacity-40 hover:border-signal/50 hover:text-signal disabled:hover:border-border disabled:hover:text-slate-400"
        >
          Next
        </button>
      </div>
    </div>
  );
}
