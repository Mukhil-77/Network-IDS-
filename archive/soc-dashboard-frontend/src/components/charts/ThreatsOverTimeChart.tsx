import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import type { ThreatsPerMinutePoint } from "../../types/statistics";

export function ThreatsOverTimeChart({ data }: { data: ThreatsPerMinutePoint[] }) {
  const formatted = data.map((point) => ({
    ...point,
    label: point.minute.slice(11), // "HH:MM" from "YYYY-MM-DDTHH:MM"
  }));

  return (
    <ResponsiveContainer width="100%" height={240}>
      <AreaChart data={formatted}>
        <defs>
          <linearGradient id="threatFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#22d3ee" stopOpacity={0.35} />
            <stop offset="95%" stopColor="#22d3ee" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#22304a" vertical={false} />
        <XAxis dataKey="label" stroke="#64748b" fontSize={11} tickLine={false} />
        <YAxis stroke="#64748b" fontSize={11} tickLine={false} allowDecimals={false} width={28} />
        <Tooltip
          contentStyle={{ background: "#111a2c", border: "1px solid #22304a", borderRadius: 8, fontSize: 12 }}
          labelStyle={{ color: "#e2e8f0" }}
        />
        <Area type="monotone" dataKey="count" stroke="#22d3ee" fill="url(#threatFill)" strokeWidth={2} />
      </AreaChart>
    </ResponsiveContainer>
  );
}
