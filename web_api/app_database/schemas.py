"""
Application Database Schemas
Pydantic models for app database operations
"""

from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    """User creation schema."""
    username: str
    password: str
    email: EmailStr
