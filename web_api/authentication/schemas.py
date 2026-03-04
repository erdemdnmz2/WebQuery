"""
Authentication Schemas
Pydantic models for authentication endpoints
"""
from pydantic import BaseModel, EmailStr
from typing import Optional


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

    class Config:
        from_attributes = True


class Token(BaseModel):
    """JWT token response schema"""
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """Token payload data"""
    sub: str  # user_id as string
