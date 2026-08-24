import { useState } from "react";

import { useThreatIndicators } from "../hooks/useThreatIntel";
import { TableSkeleton } from "../components/common/LoadingSkeleton";
import { ErrorState } from "../components/common/ErrorState";
import { formatTimestamp } from "../utils/formatters";

const TAG_CLASSES: Record<string, string> = {
  "Known Malicious": "bg-severity-critical/15 text-severity-critical border-severity-critical/30",
  Suspicious: "bg-severity-high/15 text-severity-high border-severity-high/30",
  Unknown: "bg-slate-500/15 text-slate-300 border-slate-500/30",
  Trusted: "bg-severity-benign/15 text-severity-benign border-severity-benign/30",
};

export default function ThreatIntelligence() {
  const [tag, setTag] = useState<string>("");
  const query = useThreatIndicators(tag || undefined);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-slate-100">Threat Intelligence</h1>
        <select
          value={tag} onChange={(e) => setTag(e.target.value)}
          className="rounded-md border border-border bg-surface-raised px-3 py-1.5 text-sm text-slate-100 focus:border-signal focus:outline-none"
        >
          <option value="">All tags</option>
          <option value="Known Malicious">Known Malicious</option>
          <option value="Suspicious">Suspicious</option>
          <option value="Unknown">Unknown</option>
          <option value="Trusted">Trusted</option>
        </select>
      </div>

      <p className="text-xs text-slate-500">
        Known indicators (IPs, domains, hashes) from the built-in list and any synced feeds - see the
        modular provider framework in <code className="font-mono">backend/threat_intelligence/reputation.py</code>.
      </p>

      {query.isLoading && <TableSkeleton />}
      {query.isError && <ErrorState message="Couldn't load threat indicators." onRetry={() => query.refetch()} />}
      {query.data && (
        <div className="overflow-x-auto rounded-xl border border-border">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-border bg-surface-raised text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3 font-medium">Value</th>
                <th className="px-4 py-3 font-medium">Type</th>
                <th className="px-4 py-3 font-medium">Tag</th>
                <th className="px-4 py-3 font-medium">Source</th>
                <th className="px-4 py-3 font-medium">Confidence</th>
                <th className="px-4 py-3 font-medium">Notes</th>
                <th className="px-4 py-3 font-medium">Added</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {query.data.map((indicator) => (
                <tr key={indicator.id} className="hover:bg-surface-raised/60">
                  <td className="px-4 py-2.5 font-mono text-slate-200">{indicator.value}</td>
                  <td className="px-4 py-2.5 text-slate-400">{indicator.indicator_type}</td>
                  <td className="px-4 py-2.5">
                    <span className={`inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium ${TAG_CLASSES[indicator.tag] ?? TAG_CLASSES.Unknown}`}>
                      {indicator.tag}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-slate-400">{indicator.source}</td>
                  <td className="px-4 py-2.5 font-mono text-slate-300">{indicator.confidence.toFixed(0)}%</td>
                  <td className="px-4 py-2.5 text-slate-500">{indicator.notes ?? "—"}</td>
                  <td className="px-4 py-2.5 whitespace-nowrap font-mono text-xs text-slate-500">{formatTimestamp(indicator.added_at)}</td>
                </tr>
              ))}
              {query.data.length === 0 && (
                <tr><td colSpan={7} className="px-4 py-8 text-center text-slate-500">No indicators match this filter.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
