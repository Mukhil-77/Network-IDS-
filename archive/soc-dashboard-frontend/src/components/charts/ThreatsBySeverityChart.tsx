import { PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer } from "recharts";
import { severityColor } from "../../utils/severity";

export function ThreatsBySeverityChart({ data }: { data: Record<string, number> }) {
  const formatted = Object.entries(data).map(([severity, count]) => ({ name: severity, value: count }));

  if (formatted.length === 0) {
    return <p className="flex h-60 items-center justify-center text-sm text-slate-500">No data yet</p>;
  }

  return (
    <ResponsiveContainer width="100%" height={240}>
      <PieChart>
        <Pie data={formatted} dataKey="value" nameKey="name" innerRadius={50} outerRadius={80} paddingAngle={2}>
          {formatted.map((entry) => (
            <Cell key={entry.name} fill={severityColor(entry.name)} />
          ))}
        </Pie>
        <Tooltip contentStyle={{ background: "#111a2c", border: "1px solid #22304a", borderRadius: 8, fontSize: 12 }} />
        <Legend wrapperStyle={{ fontSize: 12, color: "#94a3b8" }} />
      </PieChart>
    </ResponsiveContainer>
  );
}
