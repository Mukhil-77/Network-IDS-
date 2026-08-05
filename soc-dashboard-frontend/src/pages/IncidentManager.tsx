import { useState } from "react";

import { useCreateIncident, useIncidents, useUpdateIncident } from "../hooks/useIncidents";
import { SeverityBadge } from "../components/common/Badge";
import { IncidentStatusChart } from "../components/charts/IncidentStatusChart";
import { TableSkeleton } from "../components/common/LoadingSkeleton";
import { ErrorState } from "../components/common/ErrorState";
import { Pagination } from "../components/common/Pagination";
import { formatTimestamp } from "../utils/formatters";
import type { Incident, IncidentFilters } from "../types/incidents";

const STATUSES = ["open", "assigned", "in_progress", "resolved", "closed"];
const SEVERITIES = ["Critical", "High", "Medium", "Low"];
const PRIORITIES = ["Low", "Medium", "High", "Urgent"];

function NewIncidentForm({ onCreated }: { onCreated: () => void }) {
  const [title, setTitle] = useState("");
  const [severity, setSeverity] = useState("Medium");
  const [priority, setPriority] = useState("Medium");
  const createMutation = useCreateIncident();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await createMutation.mutateAsync({ title, severity, priority });
    setTitle("");
    onCreated();
  };

  return (
    <form onSubmit={handleSubmit} className="flex flex-wrap items-end gap-3 rounded-xl border border-border bg-surface-raised p-4">
      <div className="min-w-[240px] flex-1">
        <label className="mb-1 block text-xs text-slate-500">Title</label>
        <input
          value={title} onChange={(e) => setTitle(e.target.value)} required
          className="w-full rounded-md border border-border bg-surface-raised px-3 py-1.5 text-sm text-slate-100 focus:border-signal focus:outline-none"
        />
      </div>
      <div>
        <label className="mb-1 block text-xs text-slate-500">Severity</label>
        <select value={severity} onChange={(e) => setSeverity(e.target.value)} className="rounded-md border border-border bg-surface-raised px-3 py-1.5 text-sm text-slate-100 focus:border-signal focus:outline-none">
          {SEVERITIES.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>
      <div>
        <label className="mb-1 block text-xs text-slate-500">Priority</label>
        <select value={priority} onChange={(e) => setPriority(e.target.value)} className="rounded-md border border-border bg-surface-raised px-3 py-1.5 text-sm text-slate-100 focus:border-signal focus:outline-none">
          {PRIORITIES.map((p) => <option key={p} value={p}>{p}</option>)}
        </select>
      </div>
      <button type="submit" disabled={createMutation.isPending} className="rounded-md bg-signal px-4 py-1.5 text-sm font-medium text-surface hover:bg-signal/90 disabled:opacity-40">
        {createMutation.isPending ? "Opening…" : "Open Incident"}
      </button>
    </form>
  );
}

function IncidentRow({ incident }: { incident: Incident }) {
  const [expanded, setExpanded] = useState(false);
  const [note, setNote] = useState("");
  const updateMutation = useUpdateIncident();

  return (
    <div className="rounded-xl border border-border bg-surface-raised">
      <div className="flex flex-wrap items-center justify-between gap-3 p-4">
        <div className="min-w-[200px]">
          <button onClick={() => setExpanded((v) => !v)} className="text-sm font-medium text-slate-100 hover:text-signal">
            {incident.title}
          </button>
          <p className="text-xs text-slate-500">{incident.owner ? `Owned by ${incident.owner}` : "Unassigned"} · Created by {incident.created_by}</p>
        </div>
        <SeverityBadge severity={incident.severity} />
        <select
          value={incident.status}
          onChange={(e) => updateMutation.mutate({ id: incident.id, payload: { status: e.target.value } })}
          className="rounded-md border border-border bg-surface-overlay px-2 py-1 text-xs text-slate-200 focus:border-signal focus:outline-none"
        >
          {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <input
          placeholder="Assign owner…" defaultValue={incident.owner ?? ""}
          onBlur={(e) => e.target.value && e.target.value !== incident.owner && updateMutation.mutate({ id: incident.id, payload: { owner: e.target.value } })}
          className="w-32 rounded-md border border-border bg-surface-overlay px-2 py-1 text-xs text-slate-200 focus:border-signal focus:outline-none"
        />
      </div>

      {expanded && (
        <div className="border-t border-border p-4">
          <p className="mb-2 text-xs font-medium text-slate-400">Timeline</p>
          <ul className="mb-3 space-y-1.5 text-xs">
            {incident.timeline.map((entry, i) => (
              <li key={i} className="flex gap-2 text-slate-400">
                <span className="font-mono text-slate-600">{formatTimestamp(entry.timestamp)}</span>
                <span className="text-slate-300">{entry.actor}</span>
                <span>{entry.action}{entry.note ? `: ${entry.note}` : ""}</span>
              </li>
            ))}
          </ul>
          <div className="flex gap-2">
            <input
              value={note} onChange={(e) => setNote(e.target.value)} placeholder="Add a note…"
              className="flex-1 rounded-md border border-border bg-surface-overlay px-2 py-1 text-xs text-slate-200 focus:border-signal focus:outline-none"
            />
            <button
              onClick={() => { if (note) { updateMutation.mutate({ id: incident.id, payload: { note } }); setNote(""); } }}
              className="rounded-md border border-border px-3 py-1 text-xs text-slate-300 hover:border-signal/50 hover:text-signal"
            >
              Add Note
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default function IncidentManager() {
  const [filters, setFilters] = useState<IncidentFilters>({ page: 1, page_size: 25 });
  const query = useIncidents(filters);

  return (
    <div className="space-y-6">
      <h1 className="text-lg font-semibold text-slate-100">Incident Manager</h1>

      <NewIncidentForm onCreated={() => setFilters((f) => ({ ...f, page: 1 }))} />

      {query.data && (
        <div className="rounded-xl border border-border bg-surface-raised p-4">
          <h2 className="mb-3 text-sm font-medium text-slate-300">Incident Status</h2>
          <IncidentStatusChart incidents={query.data.items} />
        </div>
      )}

      <div className="flex flex-wrap gap-3">
        <select
          value={filters.status ?? ""} onChange={(e) => setFilters((f) => ({ ...f, status: e.target.value || undefined, page: 1 }))}
          className="rounded-md border border-border bg-surface-raised px-3 py-1.5 text-sm text-slate-100 focus:border-signal focus:outline-none"
        >
          <option value="">All statuses</option>
          {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <select
          value={filters.severity ?? ""} onChange={(e) => setFilters((f) => ({ ...f, severity: e.target.value || undefined, page: 1 }))}
          className="rounded-md border border-border bg-surface-raised px-3 py-1.5 text-sm text-slate-100 focus:border-signal focus:outline-none"
        >
          <option value="">All severities</option>
          {SEVERITIES.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>

      {query.isLoading && <TableSkeleton />}
      {query.isError && <ErrorState message="Couldn't load incidents." onRetry={() => query.refetch()} />}
      {query.data && (
        <>
          <div className="space-y-3">
            {query.data.items.map((incident) => <IncidentRow key={incident.id} incident={incident} />)}
            {query.data.items.length === 0 && (
              <div className="rounded-xl border border-dashed border-border p-10 text-center text-sm text-slate-500">No incidents match these filters.</div>
            )}
          </div>
          <Pagination page={query.data.page} pageSize={query.data.page_size} total={query.data.total} onPageChange={(page) => setFilters((f) => ({ ...f, page }))} />
        </>
      )}
    </div>
  );
}
