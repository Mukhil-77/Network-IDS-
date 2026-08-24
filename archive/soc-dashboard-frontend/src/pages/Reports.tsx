import { useState } from "react";

import { useGenerateReport, useReportTypes } from "../hooks/useReports";
import { CardSkeleton } from "../components/common/LoadingSkeleton";
import { ErrorState } from "../components/common/ErrorState";
import type { ReportGenerateRequest } from "../types/reports";

export default function Reports() {
  const typesQuery = useReportTypes();
  const generateMutation = useGenerateReport();

  const [reportType, setReportType] = useState("daily");
  const [format, setFormat] = useState<ReportGenerateRequest["format"]>("pdf");

  const handleGenerate = async () => {
    const blob = await generateMutation.mutateAsync({ report_type: reportType, format });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${reportType}_report.${format}`;
    link.click();
    URL.revokeObjectURL(url);
  };

  if (typesQuery.isLoading) return <CardSkeleton />;
  if (typesQuery.isError) return <ErrorState message="Couldn't load report types." onRetry={() => typesQuery.refetch()} />;

  return (
    <div className="space-y-6">
      <h1 className="text-lg font-semibold text-slate-100">Reports</h1>

      <div className="rounded-xl border border-border bg-surface-raised p-4">
        <h2 className="mb-3 text-sm font-medium text-slate-300">Generate a Report</h2>
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <label className="mb-1 block text-xs text-slate-500">Report Type</label>
            <select
              value={reportType} onChange={(e) => setReportType(e.target.value)}
              className="rounded-md border border-border bg-surface-raised px-3 py-1.5 text-sm text-slate-100 focus:border-signal focus:outline-none"
            >
              {typesQuery.data?.map((t) => (
                <option key={t.report_type} value={t.report_type}>{t.title}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs text-slate-500">Format</label>
            <select
              value={format} onChange={(e) => setFormat(e.target.value as ReportGenerateRequest["format"])}
              className="rounded-md border border-border bg-surface-raised px-3 py-1.5 text-sm text-slate-100 focus:border-signal focus:outline-none"
            >
              <option value="pdf">PDF</option>
              <option value="csv">CSV</option>
              <option value="json">JSON</option>
            </select>
          </div>
          <button
            onClick={handleGenerate} disabled={generateMutation.isPending}
            className="rounded-md bg-signal px-4 py-1.5 text-sm font-medium text-surface hover:bg-signal/90 disabled:opacity-40"
          >
            {generateMutation.isPending ? "Generating…" : "Generate & Download"}
          </button>
        </div>
        {generateMutation.isSuccess && <p className="mt-3 text-xs text-severity-benign">Report downloaded.</p>}
        {generateMutation.isError && <ErrorState message="Failed to generate report." />}
      </div>

      <div className="rounded-xl border border-border bg-surface-raised p-4">
        <h2 className="mb-3 text-sm font-medium text-slate-300">Available Report Types</h2>
        <ul className="divide-y divide-border text-sm">
          {typesQuery.data?.map((t) => (
            <li key={t.report_type} className="flex items-center justify-between py-2">
              <span className="text-slate-200">{t.title}</span>
              <span className="font-mono text-xs text-slate-500">{t.available_formats.join(" · ")}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
