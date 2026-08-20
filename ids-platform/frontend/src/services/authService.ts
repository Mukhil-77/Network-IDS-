import { apiClient } from "./apiClient";
import { tokenStorage } from "../utils/tokenStorage";
import type {
  AdminCreateUserRequest,
  CurrentUser,
  ForgotPasswordRequest,
  LoginRequest,
  ProfileUpdateRequest,
  RegisterRequest,
  ResetPasswordRequest,
  RoleInfo,
  TokenResponse,
} from "../types/auth";

export const authService = {
  login: async (payload: LoginRequest): Promise<CurrentUser> => {
    const { data } = await apiClient.post<TokenResponse>("/auth/login", payload);
    tokenStorage.setTokens(data.access_token, data.refresh_token);
    return authService.me();
  },

  register: async (payload: RegisterRequest): Promise<CurrentUser> => {
    const { data } = await apiClient.post<CurrentUser>("/auth/register", payload);
    return data;
  },

  logout: async (): Promise<void> => {
    const refreshToken = tokenStorage.getRefreshToken();
    if (refreshToken) {
      try {
        await apiClient.post("/auth/logout", { refresh_token: refreshToken });
      } catch {
        // Best-effort - the tokens are being cleared client-side either way.
      }
    }
    tokenStorage.clear();
  },

  me: async (): Promise<CurrentUser> => {
    const { data } = await apiClient.get<CurrentUser>("/auth/me");
    return data;
  },

  updateProfile: async (payload: ProfileUpdateRequest): Promise<CurrentUser> => {
    const { data } = await apiClient.put<CurrentUser>("/auth/profile", payload);
    return data;
  },

  forgotPassword: async (payload: ForgotPasswordRequest): Promise<{ message: string }> => {
    const { data } = await apiClient.post("/auth/forgot-password", payload);
    return data;
  },

  resetPassword: async (payload: ResetPasswordRequest): Promise<void> => {
    await apiClient.post("/auth/reset-password", payload);
  },

  listRoles: async (): Promise<RoleInfo[]> => {
    const { data } = await apiClient.get<RoleInfo[]>("/roles");
    return data;
  },

  getUsers: async (): Promise<CurrentUser[]> => {
    const { data } = await apiClient.get<CurrentUser[]>("/users");
    return data;
  },

  createUser: async (payload: AdminCreateUserRequest): Promise<CurrentUser> => {
    const { data } = await apiClient.post<CurrentUser>("/users", payload);
    return data;
  },

  updateUserRole: async (username: string, roleName: string): Promise<void> => {
    await apiClient.put(`/users/${username}/role`, { role_name: roleName });
  },

  toggleUserStatus: async (username: string, deactivate: boolean): Promise<void> => {
    if (deactivate) {
      await apiClient.post(`/users/${username}/deactivate`);
    } else {
      await apiClient.post(`/users/${username}/reactivate`);
    }
  },

  getAuditLog: async (params?: { page?: number; page_size?: number }): Promise<any> => {
    const { data } = await apiClient.get("/audit", { params });
    return data;
  },

  isAuthenticated: (): boolean => Boolean(tokenStorage.getAccessToken()),
};
