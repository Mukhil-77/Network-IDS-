// Mirrors backend/auth/schemas.py exactly.

export interface LoginRequest {
  username: string;
  password: string;
}

export interface RegisterRequest {
  username: string;
  email: string;
  password: string;
  role?: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface CurrentUser {
  id: string;
  username: string;
  email: string;
  role: string;
  is_active: boolean;
  created_at: string;
  last_login_at: string | null;
}

export interface ProfileUpdateRequest {
  email?: string;
  current_password?: string;
  new_password?: string;
}

export interface RoleInfo {
  id: string;
  name: string;
  description: string;
  permissions: string[];
}

export interface ForgotPasswordRequest {
  email: string;
}

export interface ResetPasswordRequest {
  reset_token: string;
  new_password: string;
}

export interface AuditLogEntry {
  id: number;
  timestamp: string;
  actor: string;
  action: string;
  target: string | null;
  role: string | null;
  ip_address: string | null;
  status: string;
  details: Record<string, unknown> | null;
}
