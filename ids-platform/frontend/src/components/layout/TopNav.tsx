import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useTheme } from "../../context/ThemeContext";
import { useAuth } from "../../context/AuthContext";
import { useWebSocketAlerts } from "../../context/WebSocketContext";
import { StatusDot } from "../common/StatusDot";

interface TopNavProps {
  onToggleSidebar: () => void;
}

// Zoom state stored in localStorage so it survives window restores.
const STORED_ZOOM_KEY = "soc_platform_zoom";
const DEFAULT_ZOOM = 1.0; // base zoom (Electron handles default 0.9)
const ZOOM_STEP = 0.05;

function getStoredZoom(): number {
  try {
    const stored = window.localStorage.getItem(STORED_ZOOM_KEY);
    return stored ? parseFloat(stored) : DEFAULT_ZOOM;
  } catch {
    return DEFAULT_ZOOM;
  }
}

function setStoredZoom(zoom: number) {
  try {
    window.localStorage.setItem(STORED_ZOOM_KEY, zoom.toString());
  } catch {}
}

function applyZoom(zoom: number) {
  // Clamp to reasonable bounds so the UI never becomes unmanageable.
  const clamped = Math.min(Math.max(zoom, 0.6), 2.0);
  // Use CSS zoom property (supported in Chromium/Electron) – no layout shift, no blur.
  document.documentElement.style.zoom = `${clamped}`;
  setStoredZoom(clamped);
}

export function TopNav({ onToggleSidebar }: TopNavProps) {
  const { theme, toggleTheme } = useTheme();
  const { status } = useWebSocketAlerts();
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  // Initial zoom from storage; will be applied by the effect below.
  const [zoom, setZoom] = useState(getStoredZoom);
  useEffect(() => {
    const clamped = Math.min(Math.max(zoom, 0.6), 2.0);
    document.documentElement.style.zoom = `${clamped}`;
  }, [zoom]);

  const handleLogout = async () => {
    await logout();
    navigate("/login", { replace: true });
  };

  return (
    <header
      className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-border bg-surface px-4"
    >
      <button
        onClick={onToggleSidebar}
        className="rounded-md p-1.5 text-slate-400 hover:bg-surface-overlay hover:text-slate-100 md:hidden"
        aria-label="Toggle navigation"
      >
        ☰
      </button>
      <div className="hidden md:block" />
      <div className="flex items-center gap-4">
        <StatusDot status={status} />
        <button
          onClick={toggleTheme}
          className="rounded-md border border-border px-2.5 py-1 text-xs font-medium text-slate-300 hover:border-signal/50 hover:text-signal"
          aria-label="Toggle dark mode"
        >
          {theme === "dark" ? "☾ Dark" : "☀ Light"}
        </button>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setZoom((z) => Math.min(z + ZOOM_STEP, 2.0))}
            className="rounded-md p-1.5 text-sm text-slate-300 hover:bg-surface-overlay hover:text-slate-100"
            aria-label="Zoom in"
          >
            +
          </button>
          <span className="text-sm text-slate-400">{zoom.toFixed(2)}</span>
          <button
            onClick={() => setZoom((z) => Math.max(z - ZOOM_STEP, 0.6))}
            className="rounded-md p-1.5 text-sm text-slate-300 hover:bg-surface-overlay hover:text-slate-100"
            aria-label="Zoom out"
          >
            -
          </button>
          <button
            onClick={() => setZoom(DEFAULT_ZOOM)}
            className="rounded-md p-1.5 text-xs text-slate-400 hover:bg-surface-overlay hover:text-slate-100"
            aria-label="Reset zoom"
          >
            ↻
          </button>
        </div>
        {user && (
          <div className="flex items-center gap-2 border-l border-border pl-4">
            <button
              onClick={() => navigate("/profile")}
              className="flex flex-col items-end text-right hover:opacity-80"
            >
              <span className="text-xs font-medium text-slate-200">{user.username}</span>
              <span className="text-[10px] text-slate-500">{user.role}</span>
            </button>
            <button
              onClick={handleLogout}
              className="rounded-md border border-border px-2.5 py-1 text-xs font-medium text-slate-400 hover:border-severity-critical/50 hover:text-severity-critical"
            >
              Log out
            </button>
          </div>
        )}
      </div>
    </header>
  );
}