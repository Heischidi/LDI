"""Authentication and staff user Pydantic schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LoginRequest(BaseModel):
    email: str = Field(min_length=1)
    username: str | None = None
    password: str = Field(min_length=1)


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


class UserSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    username: str | None = None
    email: str
    first_name: str
    last_name: str
    phone_number: str | None = None
    role: str
    permissions: list[str] = Field(default_factory=list)
    is_active: bool
    last_login_at: datetime | None = None
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserSummary


class UserCreateRequest(BaseModel):
    email: str | None = None
    username: str | None = None
    password: str = Field(min_length=4, max_length=128)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    phone_number: str | None = None
    role_name: str = Field(default="OFFICER", pattern="^(CEO|SUPER_ADMIN|ADMIN|OFFICER|VIEWER)$")
    is_active: bool = True


class UserUpdateRequest(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    phone_number: str | None = None
    role_name: str | None = Field(default=None, pattern="^(CEO|SUPER_ADMIN|ADMIN|OFFICER|VIEWER)$")
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=4, max_length=128)
