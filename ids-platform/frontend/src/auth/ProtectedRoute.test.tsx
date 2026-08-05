import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { QueryClientProvider, QueryClient } from "@tanstack/react-query";
import { render } from "@testing-library/react";

vi.mock("../services/authService", () => ({
  authService: {
    isAuthenticated: vi.fn(),
    me: vi.fn(),
    login: vi.fn(),
    logout: vi.fn(),
  },
}));

import { authService } from "../services/authService";
import { AuthProvider } from "../context/AuthContext";
import { ProtectedRoute } from "./ProtectedRoute";

function renderProtected(initialPath = "/dashboard") {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialPath]}>
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<div>Login Page</div>} />
            <Route path="/dashboard" element={<ProtectedRoute><div>Secret Dashboard</div></ProtectedRoute>} />
            <Route
              path="/admin-only"
              element={<ProtectedRoute requiredPermission="users:write"><div>Admin Panel</div></ProtectedRoute>}
            />
          </Routes>
        </AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("ProtectedRoute", () => {
  beforeEach(() => vi.clearAllMocks());

  it("redirects to /login when not authenticated", async () => {
    vi.mocked(authService.isAuthenticated).mockReturnValue(false);
    renderProtected("/dashboard");

    expect(await screen.findByText("Login Page")).toBeInTheDocument();
  });

  it("renders the protected content once authenticated", async () => {
    vi.mocked(authService.isAuthenticated).mockReturnValue(true);
    vi.mocked(authService.me).mockResolvedValue({
      id: "1", username: "alice", email: "a@example.com", role: "Admin",
      is_active: true, created_at: "2026-01-01T00:00:00Z", last_login_at: null,
    });
    renderProtected("/dashboard");

    expect(await screen.findByText("Secret Dashboard")).toBeInTheDocument();
  });

  it("shows an access-denied message when authenticated but lacking the required permission", async () => {
    vi.mocked(authService.isAuthenticated).mockReturnValue(true);
    vi.mocked(authService.me).mockResolvedValue({
      id: "1", username: "viewer1", email: "v@example.com", role: "Viewer",
      is_active: true, created_at: "2026-01-01T00:00:00Z", last_login_at: null,
    });
    renderProtected("/admin-only");

    expect(await screen.findByText("Access denied")).toBeInTheDocument();
    expect(screen.queryByText("Admin Panel")).not.toBeInTheDocument();
  });
});
