"""Pydantic request/response schemas for the auth API."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds until the access token expires


class RefreshRequest(BaseModel):
    refresh_token: str


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    email: EmailStr
    password: str = Field(..., min_length=8)
    # Note: self-registration is *always* Viewer regardless of what the
    # client sends - see POST /auth/register in auth/routes.py. The field
    # is intentionally absent here so a malicious client can't escalate.

    @field_validator("password")
    @classmethod
    def password_strength(cls, value: str) -> str:
        if not any(c.isupper() for c in value) or not any(c.isdigit() for c in value):
            raise ValueError("Password must contain at least one uppercase letter and one digit")
        return value


class AdminCreateUserRequest(BaseModel):
    """Body for POST /users (admin-only) - an operator-picked role is expected here."""

    username: str = Field(..., min_length=3, max_length=64)
    email: EmailStr
    password: str = Field(..., min_length=8)
    role: str = "Viewer"

    @field_validator("password")
    @classmethod
    def password_strength(cls, value: str) -> str:
        if not any(c.isupper() for c in value) or not any(c.isdigit() for c in value):
            raise ValueError("Password must contain at least one uppercase letter and one digit")
        return value


class UpdateUserRoleRequest(BaseModel):
    role_name: str


class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    role: str
    is_active: bool
    created_at: datetime
    last_login_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ProfileUpdateRequest(BaseModel):
    email: Optional[EmailStr] = None
    current_password: Optional[str] = None
    new_password: Optional[str] = Field(None, min_length=8)


class RoleResponse(BaseModel):
    id: str
    name: str
    description: str
    permissions: list[str]

    model_config = {"from_attributes": True}


class AuditLogResponse(BaseModel):
    id: int
    timestamp: datetime
    actor: str
    action: str
    target: Optional[str] = None
    role: Optional[str] = None
    ip_address: Optional[str] = None
    status: str
    details: Optional[dict] = None

    model_config = {"from_attributes": True}


class PaginatedAuditLog(BaseModel):
    items: list[AuditLogResponse]
    total: int
    page: int
    page_size: int


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    reset_token: str
    new_password: str = Field(..., min_length=8)
