"""
Application Database Schemas
Pydantic models for app database operations
"""
from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List, Dict
from datetime import datetime

class UserCreate(BaseModel):
    """Kullanıcı oluşturma şeması"""
    username: str
    password: str
    email: EmailStr

