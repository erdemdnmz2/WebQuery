"""
Authentication Service Config
"""
import os

SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-here-change-in-production")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", str(60 * 24)))
COOKIE_TOKEN_EXPIRE_MINUTES = int(os.getenv("COOKIE_TOKEN_EXPIRE_MINUTES", str(60 * 60 * 24)))
SESSION_TIMEOUT = int(os.getenv("SESSION_TIMEOUT_MINUTES", "60"))
RATE_LIMITER = os.getenv("RATE_LIMITER", "100/minute")
