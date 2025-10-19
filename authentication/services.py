"""
Authentication Service Layer
JWT token oluşturma, doğrulama ve kullanıcı yetkilendirme işlemleri
"""
from datetime import datetime, timedelta, UTC
from typing import Optional
from jose import JWTError, jwt
from fastapi import HTTPException, status, Request, Depends
from sqlalchemy.future import select

from authentication import config
from app_database.models import User
from authentication.schemas import TokenData
from dependencies import get_app_db, get_session_cache
from app_database.app_database import AppDatabase


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    JWT access token oluşturur
    
    Args:
        data: Token içeriği (genellikle {"sub": user_id})
        expires_delta: Token geçerlilik süresi (varsayılan: config.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    Returns:
        JWT token string
    """
    to_encode = data.copy()
    expire = datetime.now(UTC) + (expires_delta or timedelta(minutes=config.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, config.SECRET_KEY, algorithm=config.ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> Optional[dict]:
    """
    JWT token'ı doğrular
    
    Args:
        token: JWT token string
    
    Returns:
        Token payload veya None
    """
    try:
        payload = jwt.decode(token, config.SECRET_KEY, algorithms=[config.ALGORITHM])
        return payload
    except JWTError:
        return None


def get_user_id_from_payload(payload: dict) -> Optional[str]:
    """
    Token payload'ından user_id çıkarır
    
    Args:
        payload: JWT token payload
    
    Returns:
        User ID string veya None
    """
    try:
        user_id = payload.get("sub")
        return user_id
    except Exception:
        return None


def is_session_valid(user_id: int, session_cache: dict) -> bool:
    """
    Session'ın hala geçerli olup olmadığını kontrol eder
    
    Args:
        user_id: Kullanıcı ID
        session_cache: Session cache dictionary
    
    Returns:
        True ise session geçerli, False ise geçersiz veya süresi dolmuş
    """
    info = session_cache.get(user_id)
    if not info:
        return False
    
    timeout = timedelta(minutes=config.SESSION_TIMEOUT)
    if datetime.now() - info["addition_date"] > timeout:
        session_cache.pop(user_id, None)
        return False
    
    return True


async def get_current_user(
    request: Request,
    app_db: AppDatabase = Depends(get_app_db)
) -> User:
    """
    Request'ten JWT token alır, doğrular ve User nesnesini döndürür
    
    Dependencies:
        - get_app_db: AppDatabase instance
    
    Args:
        request: FastAPI Request nesnesi
        app_db: AppDatabase instance (injected)
    
    Returns:
        User: Authenticated user
    
    Raises:
        HTTPException: Token geçersiz veya kullanıcı bulunamaz ise
    """
    # Token'ı sadece cookie'den al
    token = request.cookies.get("access_token")
    
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Geçersiz token",
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
    except JWTError as e:
        print(f"JWT Error: {str(e)}")
        raise credentials_exception
    
    # AppDatabase'den user'ı çek
    async with app_db.get_app_db() as db:
        result = await db.execute(select(User).filter(User.id == int(token_data.sub)))
        user = result.scalars().first()
    
    if user is None:
        raise credentials_exception
    
    return user
