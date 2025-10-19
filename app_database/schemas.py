from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List, Dict
from datetime import datetime

# User schema

class UserCreate(BaseModel):
    username: str
    password: str
    email: EmailStr

