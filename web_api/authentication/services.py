"""
Authentication Service Layer
JWT token generation, verification, and user authorization operations.
"""
from datetime import datetime, timedelta, UTC
from typing import Optional
from jose import JWTError, jwt
from fastapi import HTTPException, status, Request
from sqlalchemy.future import select

from authentication import config
from app_database.models import User
from authentication.schemas import TokenData
from app_database.app_database import AppDatabase


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Generates a new JWT access token.
    
    Args:
        data: Payload content (typically {"sub": user_id}).
        expires_delta: Token expiration duration (defaults to config.ACCESS_TOKEN_EXPIRE_MINUTES).
        
    Returns:
        str: Generated JWT token string.
    """
    to_encode = data.copy()
    expire = datetime.now(UTC) + (expires_delta or timedelta(minutes=config.ACCESS_TOKEN_EXPIRE_MINUTES))
    import uuid
    jti = uuid.uuid4().hex
    to_encode.update({"exp": expire, "jti": jti})
    encoded_jwt = jwt.encode(to_encode, config.SECRET_KEY, algorithm=config.ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> Optional[dict]:
    """
    Validates a JWT token.
    
    Args:
        token: JWT token string.
        
    Returns:
        Optional[dict]: Decoded token payload if valid, otherwise None.
    """
    try:
        payload = jwt.decode(token, config.SECRET_KEY, algorithms=[config.ALGORITHM])
        return payload
    except JWTError:
        return None


def get_user_id_from_payload(payload: dict) -> Optional[str]:
    """
    Extracts the user_id (sub) from the token payload.
    
    Args:
        payload: Decoded JWT token payload.
        
    Returns:
        Optional[str]: User ID string if present, otherwise None.
    """
    try:
        user_id = payload.get("sub")
        return user_id
    except Exception:
        return None


async def get_current_user(
    request: Request
) -> User:
    """
    Extracts JWT token from Request, validates it, and returns the User object.
    
    Args:
        request: FastAPI Request object.
        
    Returns:
        User: Authenticated user.
        
    Raises:
        HTTPException: If token is invalid or user is not found.
    """
    # Retrieve AppDatabase instance from request state to prevent circular imports
    app_db: AppDatabase = request.app.state.app_db

    # Retrieve token solely from cookies
    token = request.cookies.get("access_token")
    
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid token",
        headers={"WWW-Authenticate": "Bearer"}
    )
    
    if not token:
        raise credentials_exception
    
    try:
        payload = jwt.decode(token, config.SECRET_KEY, algorithms=[config.ALGORITHM])
        user_id: str = payload.get("sub")
        jti: str = payload.get("jti")
        if user_id is None:
            raise credentials_exception
        token_data = TokenData(sub=user_id)
    except JWTError as e:
        print(f"JWT Error: {str(e)}")
        raise credentials_exception
        
    # Check if token is blacklisted
    if jti:
        is_blacklisted = await app_db.is_token_blacklisted(jti)
        if is_blacklisted:
            raise credentials_exception
    
    # Retrieve user from AppDatabase
    async with app_db.get_app_db() as db:
        result = await db.execute(select(User).filter(User.id == int(token_data.sub)))
        user = result.scalars().first()
    
    if user is None:
        raise credentials_exception
    
    return user
