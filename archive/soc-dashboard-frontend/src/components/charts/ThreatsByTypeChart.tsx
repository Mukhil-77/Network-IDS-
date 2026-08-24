import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";

export function ThreatsByTypeChart({ data }: { data: Record<string, number> }) {
  const formatted = Object.entries(data)
    .map(([attack_type, count]) => ({ attack_type, count }))
    .sort((a, b) => b.count - a.count);

  return (
    <ResponsiveContainer width="100%" height={240}>
      <BarChart data={formatted} layout="vertical" margin={{ left: 8 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#22304a" horizontal={false} />
        <XAxis type="number" stroke="#64748b" fontSize={11} allowDecimals={false} />
        <YAxis type="category" dataKey="attack_type" stroke="#64748b" fontSize={11} width={90} />
        <Tooltip contentStyle={{ background: "#111a2c", border: "1px solid #22304a", borderRadius: 8, fontSize: 12 }} />
        <Bar dataKey="count" fill="#22d3ee" radius={[0, 4, 4, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
