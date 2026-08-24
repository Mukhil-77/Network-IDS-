import { useNavigate } from "react-router-dom";

import { useAuth } from "../../context/AuthContext";

/** Shown when a background token refresh fails (see apiClient.ts's SESSION_EXPIRED_EVENT) - the user was doing something and got silently logged out; say so, rather than letting the next click quietly 401. */
export function SessionExpiredBanner() {
  const { sessionExpired, clearSessionExpired } = useAuth();
  const navigate = useNavigate();

  if (!sessionExpired) return null;

  return (
    <div className="fixed inset-x-0 top-0 z-50 flex items-center justify-center gap-3 bg-severity-high px-4 py-2 text-sm font-medium text-surface">
      <span>Your session has expired.</span>
      <button
        onClick={() => {
          clearSessionExpired();
          navigate("/login");
        }}
        className="rounded-md bg-surface/20 px-3 py-1 hover:bg-surface/30"
      >
        Log in again
      </button>
    </div>
  );
}
