import { useTheme } from "../context/ThemeContext";

export default function Settings() {
  const { theme, toggleTheme } = useTheme();

  return (
    <div className="max-w-xl space-y-6">
      <h1 className="text-lg font-semibold text-slate-100">Settings</h1>

      <div className="rounded-xl border border-border bg-surface-raised p-4">
        <h2 className="mb-3 text-sm font-medium text-slate-300">Appearance</h2>
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-slate-200">Dark mode</p>
            <p className="text-xs text-slate-500">Applies across the whole dashboard, saved to this browser.</p>
          </div>
          <button
            onClick={toggleTheme}
            className="rounded-md border border-border bg-surface-overlay px-3 py-1.5 text-sm font-medium text-slate-100 hover:border-signal/50 hover:text-signal"
          >
            {theme === "dark" ? "Switch to light" : "Switch to dark"}
          </button>
        </div>
      </div>

      <div className="rounded-xl border border-border bg-surface-raised p-4">
        <h2 className="mb-3 text-sm font-medium text-slate-300">Connection</h2>
        <dl className="grid grid-cols-2 gap-y-2 text-sm">
          <dt className="text-slate-500">API base URL</dt>
          <dd className="font-mono text-slate-300">{import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000"}</dd>
          <dt className="text-slate-500">WebSocket URL</dt>
          <dd className="font-mono text-slate-300">{import.meta.env.VITE_WS_URL ?? "ws://localhost:8000/ws/alerts"}</dd>
        </dl>
        <p className="mt-3 text-xs text-slate-500">
          Set via <code className="font-mono">VITE_API_BASE_URL</code> / <code className="font-mono">VITE_WS_URL</code> in
          <code className="font-mono"> .env</code> - see <code className="font-mono">.env.example</code>.
        </p>
      </div>
    </div>
  );
}
