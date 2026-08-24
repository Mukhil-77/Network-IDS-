import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

import { authService } from "../services/authService";
import { SESSION_EXPIRED_EVENT } from "../services/apiClient";
import { tokenStorage } from "../utils/tokenStorage";
import type { CurrentUser, LoginRequest, RegisterRequest } from "../types/auth";

interface AuthContextValue {
  user: CurrentUser | null;
  isLoading: boolean;
  sessionExpired: boolean;
  login: (payload: LoginRequest) => Promise<void>;
  register: (payload: RegisterRequest) => Promise<void>;
  logout: () => Promise<void>;
  hasPermission: (permission: string) => boolean;
  clearSessionExpired: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

// Mirrors backend/auth/permissions.py's DEFAULT_ROLE_PERMISSIONS - used
// only to decide what to *show* in the UI (hiding a nav link, disabling a
// button); the backend re-checks every permission on every request
// regardless, so this being out of sync would at worst show a link that
// 403s when clicked, never grant real access it shouldn't.
const ROLE_PERMISSIONS: Record<string, string[]> = {
  Admin: [
    "alerts:read", "alerts:write", "flows:read", "statistics:read", "predict:execute",
    "responses:read", "responses:execute", "settings:read", "settings:write",
    "users:read", "users:write", "roles:read", "audit:read",
    "reports:read", "reports:generate", "analytics:read", "threat_intel:read",
    "incidents:read", "incidents:write", "notifications:test",
  ],
  "Security Analyst": [
    "alerts:read", "alerts:write", "flows:read", "statistics:read", "predict:execute",
    "responses:read", "responses:execute", "settings:read", "audit:read",
    "reports:read", "reports:generate", "analytics:read", "threat_intel:read",
    "incidents:read", "incidents:write", "notifications:test",
  ],
  Viewer: [
    "alerts:read", "flows:read", "statistics:read",
    "reports:read", "analytics:read", "threat_intel:read", "incidents:read",
  ],
};

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [sessionExpired, setSessionExpired] = useState(false);

  useEffect(() => {
    async function restoreSession() {
      if (authService.isAuthenticated()) {
        try {
          setUser(await authService.me());
        } catch {
          tokenStorage.clear();
        }
      }
      setIsLoading(false);
    }
    restoreSession();

    const onSessionExpired = () => {
      setUser(null);
      setSessionExpired(true);
    };
    window.addEventListener(SESSION_EXPIRED_EVENT, onSessionExpired);
    return () => window.removeEventListener(SESSION_EXPIRED_EVENT, onSessionExpired);
  }, []);

  const login = async (payload: LoginRequest) => {
    const loggedInUser = await authService.login(payload);
    setUser(loggedInUser);
    setSessionExpired(false);
  };

  const register = async (payload: RegisterRequest) => {
    await authService.register(payload);
  };

  const logout = async () => {
    await authService.logout();
    setUser(null);
  };

  const hasPermission = (permission: string): boolean => {
    if (!user) return false;
    return (ROLE_PERMISSIONS[user.role] ?? []).includes(permission);
  };

  return (
    <AuthContext.Provider
      value={{ user, isLoading, sessionExpired, login, register, logout, hasPermission, clearSessionExpired: () => setSessionExpired(false) }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}
