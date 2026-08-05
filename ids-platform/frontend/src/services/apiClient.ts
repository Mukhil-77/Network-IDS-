import axios, { type AxiosError, type InternalAxiosRequestConfig } from "axios";

import { tokenStorage } from "../utils/tokenStorage";

// Single axios instance every service module shares - one place to change
// the base URL, attach auth headers, and handle token refresh/expiry.
export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000",
  timeout: 10_000,
});

// Attach the access token to every request that has one - unauthenticated
// requests (login, register, forgot-password) simply have no token yet, so
// this is a no-op for those, not a special case to branch on.
apiClient.interceptors.request.use((config) => {
  const token = tokenStorage.getAccessToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Dispatched when a session can't be silently recovered (refresh also
// failed, or there was no refresh token to try) - AuthContext listens for
// this and redirects to /login, rather than this module reaching into
// React state directly (interceptors run outside any component).
export const SESSION_EXPIRED_EVENT = "soc:session-expired";

let refreshPromise: Promise<string> | null = null;

async function refreshAccessToken(): Promise<string> {
  const refreshToken = tokenStorage.getRefreshToken();
  if (!refreshToken) {
    throw new Error("No refresh token available");
  }
  // A plain axios call, not `apiClient` itself - avoids recursing back
  // through this same response interceptor.
  const response = await axios.post(`${apiClient.defaults.baseURL}/auth/refresh`, { refresh_token: refreshToken });
  const { access_token, refresh_token } = response.data;
  tokenStorage.setTokens(access_token, refresh_token);
  return access_token;
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as (InternalAxiosRequestConfig & { _retried?: boolean }) | undefined;

    const isAuthEndpoint = originalRequest?.url?.includes("/auth/login") || originalRequest?.url?.includes("/auth/refresh");
    if (error.response?.status !== 401 || !originalRequest || originalRequest._retried || isAuthEndpoint) {
      return Promise.reject(error);
    }

    originalRequest._retried = true;
    try {
      // Multiple requests can 401 at once (e.g. a page firing several
      // queries right as the token expires) - share one in-flight refresh
      // across all of them instead of racing multiple refresh calls
      // (which would trigger refresh-token-rotation reuse detection - see
      // backend/auth/jwt_manager.py's docstring - and fail all but one).
      refreshPromise ??= refreshAccessToken().finally(() => { refreshPromise = null; });
      const newAccessToken = await refreshPromise;

      originalRequest.headers.Authorization = `Bearer ${newAccessToken}`;
      return apiClient(originalRequest);
    } catch {
      tokenStorage.clear();
      window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT));
      return Promise.reject(error);
    }
  }
);
