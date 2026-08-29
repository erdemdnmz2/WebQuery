"""
Authentication Service Layer
JWT token generation, verification, and user authorization operations.
"""
import logging

from fastapi import HTTPException, Request, status
from jose import JWTError, jwt
from sqlalchemy.future import select

from app_database.app_database import AppDatabase
from app_database.models import User
from authentication import config
from authentication.schemas import TokenData
from authentication.sessions import session_alive

logger = logging.getLogger(__name__)

# `create_access_token` was removed together with the token blacklist
# (OQ-2026-014). Access tokens are minted by `sessions.mint_access`, which binds
# them to a server-side `UserSession` row; revocation lives there.


def verify_token(token: str) -> dict | None:
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


def get_user_id_from_payload(payload: dict) -> str | None:
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
    # Retrieve AppDatabase instance from request state context to prevent circular imports
    app_db: AppDatabase = request.app.state.context.app_db

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
        if user_id is None:
            raise credentials_exception
        token_data = TokenData(sub=user_id)
    except JWTError:
        logger.warning("Geçersiz JWT reddedildi")
        raise credentials_exception

    # AuthMiddleware verifies the session once per request and records it. The
    # query is only repeated when this dependency is used without the
    # middleware — an isolated test, or a future non-middleware entry point.
    session_id = payload.get("sid")
    if session_id is not None and not getattr(request.state, "session_verified", False):
        try:
            if not await session_alive(app_db, int(session_id), int(user_id)):
                raise credentials_exception
        except (TypeError, ValueError):
            raise credentials_exception

    # AuthMiddleware loads the user once per request and shares it through
    # request.state. Keep a database fallback so this dependency remains safe
    # when called without the middleware (for example in isolated tests).
    user = getattr(request.state, "authenticated_user", None)
    if user is None:
        async with app_db.get_app_db() as db:
            result = await db.execute(select(User).filter(User.id == int(token_data.sub)))
            user = result.scalars().first()

    if user is None or not user.is_active:
        raise credentials_exception
    
    return user
