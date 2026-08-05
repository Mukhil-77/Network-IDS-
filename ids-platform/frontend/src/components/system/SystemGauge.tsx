interface SystemGaugeProps {
  percent: number;
  color: string;
  size?: number;
  label?: string;
}

/**
 * Circular progress gauge for the task-manager cards (CPU / memory / disk /
 * GPU utilization). Shows the percentage as its value text by default.
 */
export function SystemGauge({ percent, color, size = 84, label }: SystemGaugeProps) {
  const clamped = Math.max(0, Math.min(100, percent));
  const radius = (size - 10) / 2;
  const circumference = 2 * Math.PI * radius;
  const dash = (clamped / 100) * circumference;

  return (
    <svg width={size} height={size} className="shrink-0" role="img" aria-label={label ?? `${clamped.toFixed(0)}%`}>
      <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="var(--border)" strokeWidth={6} />
      <circle
        cx={size / 2}
        cy={size / 2}
        r={radius}
        fill="none"
        stroke={color}
        strokeWidth={6}
        strokeLinecap="round"
        strokeDasharray={`${dash} ${circumference - dash}`}
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
        className="transition-all duration-500"
      />
      <text
        x="50%"
        y="50%"
        textAnchor="middle"
        dominantBaseline="central"
        fontSize={size / 5.5}
        fontWeight={600}
        fontFamily="ui-monospace, monospace"
        fill="var(--text-primary)"
      >
        {clamped.toFixed(0)}%
      </text>
    </svg>
  );
}
