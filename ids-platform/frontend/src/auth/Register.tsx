import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import axios from "axios";

import { useAuth } from "../context/AuthContext";

export default function Register() {
  const { register, login } = useAuth();
  const navigate = useNavigate();

  const [form, setForm] = useState({ username: "", email: "", password: "" });
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await register(form);
      await login({ username: form.username, password: form.password });
      navigate("/", { replace: true });
    } catch (err) {
      const detail = axios.isAxiosError(err) ? err.response?.data?.detail : null;
      setError(typeof detail === "string" ? detail : "Registration failed. Check your details and try again.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-surface px-4">
      <div className="w-full max-w-sm">
        <form onSubmit={handleSubmit} className="space-y-4 rounded-xl border border-border bg-surface-raised p-6">
          <h1 className="text-lg font-semibold text-slate-100">Create an account</h1>

          {error && (
            <p className="rounded-md border border-severity-critical/30 bg-severity-critical/10 px-3 py-2 text-sm text-severity-critical">
              {error}
            </p>
          )}

          <div>
            <label className="mb-1 block text-xs text-slate-500">Username</label>
            <input
              type="text" value={form.username} onChange={(e) => setForm((f) => ({ ...f, username: e.target.value }))} required minLength={3}
              className="w-full rounded-md border border-border bg-surface-raised px-3 py-2 text-sm text-slate-100 focus:border-signal focus:outline-none"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-slate-500">Email</label>
            <input
              type="email" value={form.email} onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))} required
              className="w-full rounded-md border border-border bg-surface-raised px-3 py-2 text-sm text-slate-100 focus:border-signal focus:outline-none"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-slate-500">Password</label>
            <input
              type="password" value={form.password} onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))} required minLength={8}
              className="w-full rounded-md border border-border bg-surface-raised px-3 py-2 text-sm text-slate-100 focus:border-signal focus:outline-none"
            />
            <p className="mt-1 text-xs text-slate-600">At least 8 characters, one uppercase letter, one digit.</p>
          </div>
          <div className="rounded-md border border-border bg-surface-overlay px-3 py-2 text-xs text-slate-500">
            New accounts are created with <span className="font-medium text-slate-300">Viewer</span> access
            (read-only) by default. An administrator can grant more permissions later.
          </div>

          <button
            type="submit" disabled={isSubmitting}
            className="w-full rounded-md bg-signal py-2 text-sm font-medium text-surface hover:bg-signal/90 disabled:opacity-40"
          >
            {isSubmitting ? "Creating account…" : "Create account"}
          </button>

          <p className="text-center text-xs text-slate-500">
            Already have an account? <Link to="/login" className="text-signal hover:underline">Sign in</Link>
          </p>
        </form>
      </div>
    </div>
  );
}
