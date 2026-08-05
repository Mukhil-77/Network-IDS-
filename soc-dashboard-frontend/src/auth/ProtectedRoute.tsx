import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { useAuth } from "../context/AuthContext";

interface ProtectedRouteProps {
  children: ReactNode;
  requiredPermission?: string;
}

/**
 * Wraps a page: redirects to /login (preserving the attempted URL, so
 * Login.tsx can send the user back where they meant to go) if not
 * authenticated, or shows an inline "access denied" state if authenticated
 * but lacking `requiredPermission` - a 403, not a redirect, since the user
 * IS who they say they are, they just can't do this particular thing.
 */
export function ProtectedRoute({ children, requiredPermission }: ProtectedRouteProps) {
  const { user, isLoading, hasPermission } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return <div className="flex min-h-screen items-center justify-center bg-surface text-sm text-slate-500">Loading…</div>;
  }

  if (!user) {
    return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  }

  if (requiredPermission && !hasPermission(requiredPermission)) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-surface px-4">
        <div className="max-w-sm rounded-xl border border-severity-high/30 bg-severity-high/5 p-6 text-center">
          <p className="text-sm font-medium text-slate-100">Access denied</p>
          <p className="mt-2 text-sm text-slate-400">
            Your role ({user.role}) doesn't include the <code className="font-mono text-slate-300">{requiredPermission}</code> permission.
          </p>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
