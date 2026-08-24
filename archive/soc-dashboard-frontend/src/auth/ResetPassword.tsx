import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import axios from "axios";

import { authService } from "../services/authService";

export default function ResetPassword() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const resetToken = searchParams.get("token") ?? "";

  const [newPassword, setNewPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await authService.resetPassword({ reset_token: resetToken, new_password: newPassword });
      navigate("/login", { replace: true, state: { message: "Password reset - sign in with your new password." } });
    } catch (err) {
      const detail = axios.isAxiosError(err) ? err.response?.data?.detail : null;
      setError(typeof detail === "string" ? detail : "This reset link is invalid or has expired.");
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!resetToken) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-surface px-4">
        <div className="w-full max-w-sm rounded-xl border border-border bg-surface-raised p-6 text-center">
          <p className="text-sm text-slate-300">No reset token provided.</p>
          <Link to="/forgot-password" className="mt-3 inline-block text-sm text-signal hover:underline">Request a new reset link</Link>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-surface px-4">
      <div className="w-full max-w-sm">
        <form onSubmit={handleSubmit} className="space-y-4 rounded-xl border border-border bg-surface-raised p-6">
          <h1 className="text-lg font-semibold text-slate-100">Set a new password</h1>

          {error && (
            <p className="rounded-md border border-severity-critical/30 bg-severity-critical/10 px-3 py-2 text-sm text-severity-critical">
              {error}
            </p>
          )}

          <div>
            <label className="mb-1 block text-xs text-slate-500">New password</label>
            <input
              type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} required minLength={8} autoFocus
              className="w-full rounded-md border border-border bg-surface-raised px-3 py-2 text-sm text-slate-100 focus:border-signal focus:outline-none"
            />
          </div>

          <button
            type="submit" disabled={isSubmitting}
            className="w-full rounded-md bg-signal py-2 text-sm font-medium text-surface hover:bg-signal/90 disabled:opacity-40"
          >
            {isSubmitting ? "Resetting…" : "Reset password"}
          </button>
        </form>
      </div>
    </div>
  );
}
