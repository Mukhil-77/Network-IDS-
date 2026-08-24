import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, fireEvent, waitFor } from "@testing-library/react";
import { render } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { QueryClientProvider, QueryClient } from "@tanstack/react-query";

vi.mock("../services/authService", () => ({
  authService: {
    isAuthenticated: vi.fn().mockReturnValue(false),
    login: vi.fn(),
    me: vi.fn(),
  },
}));

import { authService } from "../services/authService";
import { AuthProvider } from "../context/AuthContext";
import Login from "./Login";

function renderLogin() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/login"]}>
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/" element={<div>Dashboard Home</div>} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("Login", () => {
  beforeEach(() => vi.clearAllMocks());

  it("submits credentials and navigates home on success", async () => {
    vi.mocked(authService.login).mockResolvedValue({
      id: "1", username: "admin", email: "a@example.com", role: "Admin",
      is_active: true, created_at: "2026-01-01T00:00:00Z", last_login_at: null,
    });
    renderLogin();

    fireEvent.change(screen.getAllByRole("textbox")[0], { target: { value: "admin" } });
    fireEvent.change(document.querySelector('input[type="password"]')!, { target: { value: "ChangeMe123!" } });
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() => expect(authService.login).toHaveBeenCalledWith({ username: "admin", password: "ChangeMe123!" }));
    expect(await screen.findByText("Dashboard Home")).toBeInTheDocument();
  });

  it("shows an error message on invalid credentials", async () => {
    vi.mocked(authService.login).mockRejectedValue(new Error("401"));
    renderLogin();

    fireEvent.change(screen.getAllByRole("textbox")[0], { target: { value: "admin" } });
    fireEvent.change(document.querySelector('input[type="password"]')!, { target: { value: "wrong" } });
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));

    expect(await screen.findByText(/invalid username or password/i)).toBeInTheDocument();
  });
});
