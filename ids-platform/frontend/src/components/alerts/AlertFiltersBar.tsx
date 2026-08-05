import type { AlertFilters } from "../../types/alert";
import { SearchInput } from "../common/SearchInput";

interface AlertFiltersBarProps {
  filters: AlertFilters;
  onChange: (filters: AlertFilters) => void;
}

const SEVERITY_OPTIONS = ["Critical", "High", "Medium", "Low"];

export function AlertFiltersBar({ filters, onChange }: AlertFiltersBarProps) {
  const update = (patch: Partial<AlertFilters>) => onChange({ ...filters, ...patch, page: 1 });

  const hasActiveFilters = Boolean(
    filters.attack_type || filters.source_ip || filters.destination_ip || filters.severity || filters.min_confidence
  );

  return (
    <div className="flex flex-wrap items-center gap-3 rounded-xl border border-border bg-surface-raised p-3">
      <div className="w-48">
        <SearchInput
          value={filters.attack_type ?? ""}
          onChange={(value) => update({ attack_type: value || undefined })}
          placeholder="Attack type…"
        />
      </div>
      <div className="w-40">
        <SearchInput
          value={filters.source_ip ?? ""}
          onChange={(value) => update({ source_ip: value || undefined })}
          placeholder="Source IP…"
        />
      </div>
      <div className="w-40">
        <SearchInput
          value={filters.destination_ip ?? ""}
          onChange={(value) => update({ destination_ip: value || undefined })}
          placeholder="Destination IP…"
        />
      </div>
      <select
        value={filters.severity ?? ""}
        onChange={(e) => update({ severity: e.target.value || undefined })}
        className="rounded-md border border-border bg-surface-raised px-3 py-1.5 text-sm text-slate-100 focus:border-signal focus:outline-none"
      >
        <option value="">All severities</option>
        {SEVERITY_OPTIONS.map((s) => (
          <option key={s} value={s}>{s}</option>
        ))}
      </select>
      <label className="flex items-center gap-2 text-sm text-slate-400">
        Min. confidence
        <input
          type="number"
          min={0}
          max={100}
          value={filters.min_confidence ?? ""}
          onChange={(e) => update({ min_confidence: e.target.value ? Number(e.target.value) : undefined })}
          className="w-16 rounded-md border border-border bg-surface-raised px-2 py-1 text-sm text-slate-100 focus:border-signal focus:outline-none"
        />
      </label>
      {hasActiveFilters && (
        <button
          onClick={() => onChange({ page: 1, page_size: filters.page_size, sort_by: filters.sort_by, sort_desc: filters.sort_desc })}
          className="ml-auto text-xs font-medium text-slate-500 hover:text-signal"
        >
          Clear filters
        </button>
      )}
    </div>
  );
}
