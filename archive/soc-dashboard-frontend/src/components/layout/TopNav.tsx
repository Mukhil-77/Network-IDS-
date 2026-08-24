import { useNavigate } from "react-router-dom";

import { useTheme } from "../../context/ThemeContext";
import { useAuth } from "../../context/AuthContext";
import { useWebSocketAlerts } from "../../context/WebSocketContext";
import { StatusDot } from "../common/StatusDot";

interface TopNavProps {
  onToggleSidebar: () => void;
}

export function TopNav({ onToggleSidebar }: TopNavProps) {
  const { theme, toggleTheme } = useTheme();
  const { status } = useWebSocketAlerts();
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate("/login", { replace: true });
  };

  return (
    <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-border bg-surface/80 px-4 backdrop-blur">
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
