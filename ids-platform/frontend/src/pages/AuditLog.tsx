import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { authService } from "../services/authService";

export function AuditLog() {
  const [page, setPage] = useState(1);
  const pageSize = 50;

  const auditQuery = useQuery({
    queryKey: ["auditLog", page],
    queryFn: () => authService.getAuditLog({ page, page_size: pageSize }),
  });

  const exportCSV = () => {
    if (!auditQuery.data?.items) return;
    
    const headers = ["Timestamp", "User", "Action", "Resource", "IP Address"];
    const rows = auditQuery.data.items.map((log: any) => [
      log.timestamp,
      log.username || "System",
      log.action,
      log.resource || "N/A",
      log.ip_address || "N/A"
    ]);
    
    const csvContent = [
      headers.join(","),
      ...rows.map((row: any[]) => row.join(","))
    ].join("\n");
    
    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.setAttribute("href", url);
    link.setAttribute("download", `audit_log_${new Date().toISOString().split('T')[0]}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="space-y-6">
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-100">Audit Log</h1>
            <p className="text-gray-400 mt-2">
              Review system access and administrative actions.
            </p>
          </div>
          <button
            onClick={exportCSV}
            disabled={!auditQuery.data?.items?.length}
            className="bg-gray-800 hover:bg-gray-700 text-slate-100 font-medium py-2 px-4 rounded-lg border border-gray-700 transition-colors disabled:opacity-50"
          >
            Export CSV
          </button>
        </div>

        <div className="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-gray-300">
              <thead className="bg-gray-900/50 text-xs uppercase text-gray-400 border-b border-gray-700">
                <tr>
                  <th className="px-6 py-4 font-medium">Timestamp</th>
                  <th className="px-6 py-4 font-medium">User</th>
                  <th className="px-6 py-4 font-medium">Action</th>
                  <th className="px-6 py-4 font-medium">Resource</th>
                  <th className="px-6 py-4 font-medium">IP Address</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-700">
                {auditQuery.isLoading ? (
                  <tr>
                    <td colSpan={5} className="px-6 py-8 text-center text-gray-500">
                      Loading audit logs...
                    </td>
                  </tr>
                ) : auditQuery.data?.items?.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="px-6 py-8 text-center text-gray-500">
                      No audit logs found.
                    </td>
                  </tr>
                ) : auditQuery.data?.items?.map((log: any) => (
                  <tr key={log.id} className="hover:bg-gray-700/50 transition-colors">
                    <td className="px-6 py-4 whitespace-nowrap text-gray-400">
                      {new Date(log.timestamp).toLocaleString()}
                    </td>
                    <td className="px-6 py-4 font-medium text-slate-100">
                      {log.username || <span className="text-gray-500">System</span>}
                    </td>
                    <td className="px-6 py-4">
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-500/10 text-blue-400 border border-blue-500/20">
                        {log.action}
                      </span>
                    </td>
                    <td className="px-6 py-4 font-mono text-xs">{log.resource || "—"}</td>
                    <td className="px-6 py-4 font-mono text-xs text-gray-400">{log.ip_address || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          
          {/* Pagination */}
          {auditQuery.data?.total > pageSize && (
            <div className="px-6 py-4 border-t border-gray-700 flex items-center justify-between">
              <span className="text-sm text-gray-400">
                Showing {((page - 1) * pageSize) + 1} to {Math.min(page * pageSize, auditQuery.data.total)} of {auditQuery.data.total} entries
              </span>
              <div className="flex gap-2">
                <button
                  onClick={() => setPage(p => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="px-3 py-1 bg-gray-900 border border-gray-700 rounded text-sm text-gray-300 disabled:opacity-50"
                >
                  Previous
                </button>
                <button
                  onClick={() => setPage(p => p + 1)}
                  disabled={page * pageSize >= auditQuery.data.total}
                  className="px-3 py-1 bg-gray-900 border border-gray-700 rounded text-sm text-gray-300 disabled:opacity-50"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </div>
    </div>
  );
}
