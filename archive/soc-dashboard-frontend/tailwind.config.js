/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        // "Ops room" palette: deep slate-navy background (not pure black -
        // pure black crushes contrast on dense data tables), a signal-cyan
        // accent for live/operational state (distinct from the generic
        // AI-cliché terracotta), and explicit semantic severity colors so
        // an analyst can triage by color alone at a glance.
        surface: {
          DEFAULT: "#0b1220",
          raised: "#111a2c",
          overlay: "#182238",
        },
        border: {
          DEFAULT: "#22304a",
        },
        signal: {
          DEFAULT: "#22d3ee",
          dim: "#0e7490",
        },
        severity: {
          critical: "#f43f5e",
          high: "#f97316",
          medium: "#eab308",
          low: "#38bdf8",
          benign: "#34d399",
        },
      },
      fontFamily: {
        // A utility monospace for IDs/IPs/timestamps/counts (genuinely aids
        // scanning tabular network data - not decorative), paired with a
        // clean grotesk for UI chrome and labels.
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "monospace"],
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
      },
      animation: {
        "pulse-live": "pulse-live 2s cubic-bezier(0.4, 0, 0.6, 1) infinite",
      },
      keyframes: {
        "pulse-live": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.4" },
        },
      },
    },
  },
  plugins: [],
};
