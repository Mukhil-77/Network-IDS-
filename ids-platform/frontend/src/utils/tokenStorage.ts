// Centralizes where tokens live (localStorage) so nothing else in the app
// touches localStorage directly - swapping storage strategy later (e.g. to
// an httpOnly-cookie + BFF pattern, which avoids the XSS-exposure tradeoff
// noted in docs/FRONTEND_ARCHITECTURE.md) means changing only this file.

const ACCESS_TOKEN_KEY = "soc_access_token";
const REFRESH_TOKEN_KEY = "soc_refresh_token";

export const tokenStorage = {
  getAccessToken: (): string | null => localStorage.getItem(ACCESS_TOKEN_KEY),
  getRefreshToken: (): string | null => localStorage.getItem(REFRESH_TOKEN_KEY),
  setTokens: (accessToken: string, refreshToken: string): void => {
    localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
    localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
  },
  clear: (): void => {
    localStorage.removeItem(ACCESS_TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
  },
};
