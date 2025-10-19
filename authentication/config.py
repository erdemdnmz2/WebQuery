"""
Authentication Service Config
"""
SECRET_KEY = "your-secret-key-here-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24
COOKIE_TOKEN_EXPIRE_MINUTES = 60 * 60 * 24
SESSION_TIMEOUT = 60
RATE_LIMITER = "100/minute"
