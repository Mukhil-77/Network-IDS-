import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "../context/AuthContext";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const redirectTo = (location.state as { from?: string } | null)?.from ?? "/";

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await login({ username, password });
      navigate(redirectTo, { replace: true });
    } catch {
      setError("Invalid username or password.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-surface px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex items-center justify-center gap-2">
          <span className="h-2.5 w-2.5 rounded-full bg-signal shadow-[0_0_10px_theme(colors.signal.DEFAULT)]" />
          <span className="font-mono text-sm font-semibold tracking-wide text-slate-100">SOC · DASHBOARD</span>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4 rounded-xl border border-border bg-surface-raised p-6">
          <h1 className="text-lg font-semibold text-slate-100">Sign in</h1>

          {error && (
            <p className="rounded-md border border-severity-critical/30 bg-severity-critical/10 px-3 py-2 text-sm text-severity-critical">
              {error}
            </p>
          )}

          <div>
            <label className="mb-1 block text-xs text-slate-500">Username</label>
            <input
              type="text" value={username} onChange={(e) => setUsername(e.target.value)} required autoFocus
              className="w-full rounded-md border border-border bg-surface-raised px-3 py-2 text-sm text-slate-100 focus:border-signal focus:outline-none focus:ring-1 focus:ring-signal"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-slate-500">Password</label>
            <input
              type="password" value={password} onChange={(e) => setPassword(e.target.value)} required
              className="w-full rounded-md border border-border bg-surface-raised px-3 py-2 text-sm text-slate-100 focus:border-signal focus:outline-none focus:ring-1 focus:ring-signal"
            />
          </div>

          <button
            type="submit" disabled={isSubmitting}
            className="w-full rounded-md bg-signal py-2 text-sm font-medium text-surface hover:bg-signal/90 disabled:opacity-40"
          >
            {isSubmitting ? "Signing in…" : "Sign in"}
          </button>

          <div className="flex items-center justify-between text-xs">
            <Link to="/forgot-password" className="text-slate-500 hover:text-signal">Forgot password?</Link>
            <Link to="/register" className="text-slate-500 hover:text-signal">Create an account</Link>
          </div>
        </form>
      </div>
    </div>
  );
}
