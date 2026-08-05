import { PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer } from "recharts";
import type { Incident } from "../../types/incidents";

const STATUS_COLORS: Record<string, string> = {
  open: "#f97316",
  assigned: "#eab308",
  in_progress: "#22d3ee",
  resolved: "#34d399",
  closed: "#64748b",
};

export function IncidentStatusChart({ incidents }: { incidents: Incident[] }) {
  const counts: Record<string, number> = {};
  incidents.forEach((i) => { counts[i.status] = (counts[i.status] ?? 0) + 1; });
  const data = Object.entries(counts).map(([name, value]) => ({ name, value }));

  if (data.length === 0) {
    return <p className="flex h-60 items-center justify-center text-sm text-slate-500">No incidents yet</p>;
  }

  return (
    <ResponsiveContainer width="100%" height={240}>
      <PieChart>
        <Pie data={data} dataKey="value" nameKey="name" innerRadius={50} outerRadius={80} paddingAngle={2}>
          {data.map((entry) => (
            <Cell key={entry.name} fill={STATUS_COLORS[entry.name] ?? "#94a3b8"} />
          ))}
        </Pie>
        <Tooltip contentStyle={{ background: "#111a2c", border: "1px solid #22304a", borderRadius: 8, fontSize: 12 }} />
        <Legend wrapperStyle={{ fontSize: 12, color: "#94a3b8" }} />
      </PieChart>
    </ResponsiveContainer>
  );
}
