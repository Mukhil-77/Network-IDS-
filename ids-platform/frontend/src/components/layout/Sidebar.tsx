import { NavLink } from "react-router-dom";
import clsx from "clsx";

import { useAuth } from "../../context/AuthContext";

// `permission: null` means "visible to anyone logged in" - no specific
// permission gate. Every other entry matches the permission its route in
// App.tsx requires, so a hidden link and a 403-on-click can never disagree.
const NAV_ITEMS: { to: string; label: string; icon: string; permission: string | null }[] = [
  { to: "/", label: "Dashboard", icon: "◧", permission: null },
  { to: "/alerts", label: "Live Alerts", icon: "▲", permission: "alerts:read" },
  { to: "/flows", label: "Flows", icon: "↔", permission: "flows:read" },
  { to: "/models", label: "Models", icon: "⎔", permission: null },
  { to: "/testing", label: "Attack Simulation", icon: "🎯", permission: "predict:execute" },
  { to: "/statistics", label: "Statistics", icon: "▤", permission: "statistics:read" },
  { to: "/analytics", label: "Analytics", icon: "◈", permission: "analytics:read" },
  { to: "/reports", label: "Reports", icon: "▦", permission: "reports:read" },
  { to: "/threat-intelligence", label: "Threat Intelligence", icon: "☣", permission: "threat_intel:read" },
  { to: "/incidents", label: "Incident Manager", icon: "▶", permission: "incidents:read" },
  { to: "/system-health", label: "System Health", icon: "◎", permission: null },
  { to: "/response-center", label: "Response Center", icon: "⚡", permission: "responses:execute" },
  { to: "/response-history", label: "Response History", icon: "☰", permission: "responses:read" },
  { to: "/policy-manager", label: "Policy Manager", icon: "◆", permission: "settings:write" },
  { to: "/notification-settings", label: "Notification Settings", icon: "✉", permission: "notifications:test" },
  { to: "/users", label: "User Management", icon: "👥", permission: "users:read" },
  { to: "/audit", label: "Audit Log", icon: "📜", permission: "audit:read" },
  { to: "/settings", label: "Settings", icon: "⚙", permission: null },
];

export function Sidebar({ open }: { open: boolean }) {
  const { hasPermission } = useAuth();
  const visibleItems = NAV_ITEMS.filter((item) => item.permission === null || hasPermission(item.permission));

  return (
    <aside
      className={clsx(
        "fixed inset-y-0 left-0 z-40 w-56 transform border-r border-border bg-surface-raised transition-transform duration-200 md:fixed md:translate-x-0",
        open ? "translate-x-0" : "-translate-x-full"
      )}
    >
      <div className="flex h-14 items-center gap-2 border-b border-border px-4">
        <span className="h-2 w-2 rounded-full bg-signal shadow-[0_0_8px_theme(colors.signal.DEFAULT)]" />
        <span className="font-mono text-sm font-semibold tracking-wide text-slate-100">SOC · DASHBOARD</span>
      </div>
      <nav className="flex flex-col gap-0.5 p-2">
        {visibleItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === "/"}
            className={({ isActive }) =>
              clsx(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "bg-signal/10 text-signal"
                  : "text-slate-400 hover:bg-surface-overlay hover:text-slate-100"
              )
            }
          >
            <span aria-hidden className="font-mono text-base">{item.icon}</span>
            {item.label}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
