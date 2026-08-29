"""
Authentication Schemas
Pydantic models for authentication endpoints
"""

from pydantic import BaseModel, EmailStr


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


class TokenData(BaseModel):
    """Token payload data"""
    sub: str  # user_id as string
