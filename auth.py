from datetime import datetime, timedelta, UTC
from typing import Optional
from jose import JWTError, jwt

from fastapi import HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from fastapi import Request

from database import get_app_db
from schemas import TokenData
import models
import config
from sqlalchemy.future import select
from database import session_cache

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

def create_access_token(data: dict, expires_delta: Optional[timedelta]= None):
    to_encode = data.copy()
    expire = datetime.now(UTC) + (expires_delta or timedelta(minutes=config.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp" : expire})
    encoded_jwt = jwt.encode(to_encode, config.SECRET_KEY, algorithm=config.ALGORITHM)
    return encoded_jwt

async def get_current_user(request: Request):
    token = request.cookies.get("access_token")
    credentials_exception = HTTPException(
        status_code= status.HTTP_401_UNAUTHORIZED,
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
        print(str(e))
        raise credentials_exception
    async with get_app_db() as db:
        user = await db.execute(select(models.User).filter(models.User.id == int(token_data.sub)))
        user = user.scalars().first()
    if user is None:
        raise credentials_exception
    return user

def verify_token(token: str):
    try:
        payload = jwt.decode(token, config.SECRET_KEY, algorithms=[config.ALGORITHM])
        return payload
    except JWTError:
        return None
    
def get_user_id(payload: dict):
    try:
        user_id = payload.get("sub")
        return user_id
    except Exception:
        return None
    
def is_session_valid(user_id):
    info = session_cache.get(user_id)
    if not info:
        return False
    timeout = timedelta(minutes=config.SESSION_TIMEOUT)
    if datetime.now() - info["addition_date"] > timeout:
        session_cache.pop(user_id, None)
        return False
    return True