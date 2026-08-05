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
        //
        // The theme-dependent tokens (surface/border/signal + the text
        // shades) resolve to CSS variables defined in src/index.css - dark
        // values on :root, light values under `html:not(.dark)` - so the
        // whole palette flips when ThemeContext toggles the `.dark` class.
        // This is why slate/gray utilities here point at variables rather
        // than Tailwind's fixed scales (kept separate from severity colors,
        // which are semantic and identical in both themes).
        surface: {
          DEFAULT: "var(--surface)",
          raised: "var(--surface-raised)",
          overlay: "var(--surface-overlay)",
        },
        border: {
          DEFAULT: "var(--border)",
        },
        signal: {
          DEFAULT: "var(--signal)",
          dim: "#0e7490",
        },
        severity: {
          critical: "#f43f5e",
          high: "#f97316",
          medium: "#eab308",
          low: "#38bdf8",
          benign: "#34d399",
        },
        // Foreground shades. Tailwind's own slate/gray scales still exist for
        // anything fixed (progress tracks, chart internals), but every
        // text/border/surface use in this app routes through these remapped
        // keys so light mode doesn't leave white text on white cards.
        slate: {
          100: "var(--text-primary)",
          200: "var(--text-primary)",
          300: "var(--text-secondary)",
          400: "var(--text-muted)",
          500: "var(--text-subtle)",
          600: "var(--text-faint)",
        },
        gray: {
          200: "var(--text-primary)",
          300: "var(--text-secondary)",
          400: "var(--text-subtle)",
          500: "var(--text-subtle)",
          600: "var(--border)",
          700: "var(--border)",
          800: "var(--surface-raised)",
          900: "var(--surface-overlay)",
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
