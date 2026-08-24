import { useState } from "react";
import { Link } from "react-router-dom";

import { authService } from "../services/authService";

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    try {
      const result = await authService.forgotPassword({ email });
      setMessage(result.message);
    } catch {
      // The backend always returns the same generic response (see
      // auth/routes.py's forgot_password - no user enumeration) - a
      // network-level failure is the only way this branch is reached.
      setMessage("If that email is registered, a reset link has been sent.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-surface px-4">
      <div className="w-full max-w-sm">
        <form onSubmit={handleSubmit} className="space-y-4 rounded-xl border border-border bg-surface-raised p-6">
          <h1 className="text-lg font-semibold text-slate-100">Reset your password</h1>
          <p className="text-xs text-slate-500">
            Enter your account email. This is a placeholder flow - no email is actually sent in this deployment
            (see backend/auth/routes.py's forgot_password docstring).
          </p>

          {message ? (
            <p className="rounded-md border border-signal/30 bg-signal/10 px-3 py-2 text-sm text-signal">{message}</p>
          ) : (
            <>
              <div>
                <label className="mb-1 block text-xs text-slate-500">Email</label>
                <input
                  type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoFocus
                  className="w-full rounded-md border border-border bg-surface-raised px-3 py-2 text-sm text-slate-100 focus:border-signal focus:outline-none"
                />
              </div>
              <button
                type="submit" disabled={isSubmitting}
                className="w-full rounded-md bg-signal py-2 text-sm font-medium text-surface hover:bg-signal/90 disabled:opacity-40"
              >
                {isSubmitting ? "Sending…" : "Send reset link"}
              </button>
            </>
          )}

          <p className="text-center text-xs text-slate-500">
            <Link to="/login" className="text-signal hover:underline">Back to sign in</Link>
          </p>
        </form>
      </div>
    </div>
  );
}
