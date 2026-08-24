import { useState } from "react";
import axios from "axios";

import { useAuth } from "../context/AuthContext";
import { authService } from "../services/authService";

export default function Profile() {
  const { user } = useAuth();
  const [email, setEmail] = useState(user?.email ?? "");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [message, setMessage] = useState<{ text: string; isError: boolean } | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (!user) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setMessage(null);
    setIsSubmitting(true);
    try {
      await authService.updateProfile({
        email: email !== user.email ? email : undefined,
        current_password: newPassword ? currentPassword : undefined,
        new_password: newPassword || undefined,
      });
      setMessage({ text: "Profile updated.", isError: false });
      setCurrentPassword("");
      setNewPassword("");
    } catch (err) {
      const detail = axios.isAxiosError(err) ? err.response?.data?.detail : null;
      setMessage({ text: typeof detail === "string" ? detail : "Update failed.", isError: true });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="max-w-xl space-y-6">
      <h1 className="text-lg font-semibold text-slate-100">Profile</h1>

      <div className="rounded-xl border border-border bg-surface-raised p-4">
        <dl className="grid grid-cols-2 gap-y-2 text-sm">
          <dt className="text-slate-500">Username</dt>
          <dd className="font-mono text-slate-200">{user.username}</dd>
          <dt className="text-slate-500">Role</dt>
          <dd className="font-mono text-slate-200">{user.role}</dd>
          <dt className="text-slate-500">Member since</dt>
          <dd className="font-mono text-slate-200">{new Date(user.created_at).toLocaleDateString()}</dd>
          <dt className="text-slate-500">Last login</dt>
          <dd className="font-mono text-slate-200">{user.last_login_at ? new Date(user.last_login_at).toLocaleString() : "—"}</dd>
        </dl>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4 rounded-xl border border-border bg-surface-raised p-4">
        <h2 className="text-sm font-medium text-slate-300">Update Profile</h2>

        {message && (
          <p className={`rounded-md border px-3 py-2 text-sm ${message.isError ? "border-severity-critical/30 bg-severity-critical/10 text-severity-critical" : "border-signal/30 bg-signal/10 text-signal"}`}>
            {message.text}
          </p>
        )}

        <div>
          <label className="mb-1 block text-xs text-slate-500">Email</label>
          <input
            type="email" value={email} onChange={(e) => setEmail(e.target.value)}
            className="w-full rounded-md border border-border bg-surface-raised px-3 py-2 text-sm text-slate-100 focus:border-signal focus:outline-none"
          />
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="mb-1 block text-xs text-slate-500">Current password</label>
            <input
              type="password" value={currentPassword} onChange={(e) => setCurrentPassword(e.target.value)}
              className="w-full rounded-md border border-border bg-surface-raised px-3 py-2 text-sm text-slate-100 focus:border-signal focus:outline-none"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-slate-500">New password</label>
            <input
              type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} minLength={8}
              className="w-full rounded-md border border-border bg-surface-raised px-3 py-2 text-sm text-slate-100 focus:border-signal focus:outline-none"
            />
          </div>
        </div>

        <button
          type="submit" disabled={isSubmitting}
          className="rounded-md bg-signal px-4 py-1.5 text-sm font-medium text-surface hover:bg-signal/90 disabled:opacity-40"
        >
          {isSubmitting ? "Saving…" : "Save changes"}
        </button>
      </form>
    </div>
  );
}
