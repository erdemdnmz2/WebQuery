"""
Application Database Schemas
Pydantic models for app database operations
"""

from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    """Kullanıcı oluşturma şeması"""
    username: str
    password: str
    email: EmailStr

