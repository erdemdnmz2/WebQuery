"""
Authentication Schemas
Pydantic models for authentication endpoints
"""

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserLogin(BaseModel):
    """Login request schema"""
    email: EmailStr
    password: str


class UserCreate(BaseModel):
    """User registration schema"""
    username: str
    email: EmailStr
    password: str


class User(BaseModel):
    """User response schema"""
    username: str
    is_admin: bool
    is_platform_owner: bool = False

    class Config:
        from_attributes = True


class LoginResponse(BaseModel):
    """Successful login acknowledgement; authentication material is cookie-only."""

    ok: bool = True


class PasswordChangeRequest(BaseModel):
    """Self-service password change.

    The current password is required so a stolen session cannot lock the real
    owner out of their own account.
    """

    model_config = ConfigDict(extra="forbid")

    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=12, max_length=256)


class PasswordChangeResponse(BaseModel):
    success: bool = True
    message: str
    #: Other sessions ended by the change; the caller's own is kept.
    revoked_sessions: int = 0


class TokenData(BaseModel):
    """Token payload data"""
    sub: str  # user_id as string
