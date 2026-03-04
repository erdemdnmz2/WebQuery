"""
Authentication Router
Login, register and user information endpoints
"""
from fastapi import APIRouter, HTTPException, Response, Request, Depends
from datetime import datetime
from cryptography.fernet import Fernet
from slowapi import Limiter
from slowapi.util import get_remote_address

from authentication import config
from authentication import schemas
from authentication.services import create_access_token, get_current_user
from dependencies import get_app_db, get_db_provider, get_session_cache, get_fernet
from session.session_cache import SessionCache
from app_database.app_database import AppDatabase
from database_provider import DatabaseProvider

router = APIRouter(prefix="/api")

limiter = Limiter(key_func=get_remote_address)


@router.post("/login", response_model=schemas.Token)
@limiter.limit(config.RATE_LIMITER)
async def login(
    user: schemas.UserLogin,
    response: Response,
    request: Request,
    app_db: AppDatabase = Depends(get_app_db),
    db_provider: DatabaseProvider = Depends(get_db_provider),
    session_cache: SessionCache = Depends(get_session_cache),
    fernet: Fernet = Depends(get_fernet)
):
    """
    User login endpoint.
    
    Verifies credentials, creates JWT token, and initializes user session.
    """
    async with app_db.get_app_db() as db:
        from app_database.models import User
        from sqlalchemy.future import select
        
        result = await db.execute(select(User).where(User.email == user.email))
        authenticated_user = result.scalars().first()
        
        if not authenticated_user or not authenticated_user.check_password(user.password):
            raise HTTPException(status_code=400, detail="Invalid email or password")
        
        user_id = int(authenticated_user.id)
        username = str(authenticated_user.username)
        
        # Create JWT token
        user_to_login = {"sub": str(user_id)}
        token = create_access_token(user_to_login)
        
        response.set_cookie(
            key="access_token",
            value=token,
            secure=False,
            samesite="strict",
            httponly=True,
            max_age=config.COOKIE_TOKEN_EXPIRE_MINUTES
        )
        
        client_ip = request.client.host
        await app_db.create_login_log(user_id=user_id, client_ip=client_ip)
        
        session_cache.add_to_cache(password=user.password, user_id=user_id)
        
        return {"access_token": token}


@router.post("/register")
@limiter.limit(config.RATE_LIMITER)
async def register(
    user: schemas.UserCreate,
    response: Response,
    request: Request,
    app_db: AppDatabase = Depends(get_app_db),
    db_provider: DatabaseProvider = Depends(get_db_provider)
):
    """
    New user registration endpoint.
    
    Registers a new user if the email is not already taken.
    """
    async with app_db.get_app_db() as db:
        from app_database.models import User
        from sqlalchemy.future import select
        
        result = await db.execute(select(User).where(User.email == user.email))
        existing_user = result.scalars().first()
        
        if existing_user:
            raise HTTPException(status_code=400, detail="Email already registered")
        
        new_user = User(
            username=user.username,
            email=user.email
        )
        new_user.set_password(user.password)

        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
        
        return {
            "success": True,
            "message": "Registration successful! Redirecting to login page..."
        }


@router.get("/me", response_model=schemas.User)
async def read_users_me(current_user=Depends(get_current_user)):
    """
    Returns current user information.
    """
    return schemas.User(
        username=current_user.username,
        is_admin=current_user.is_admin if current_user.is_admin is not None else False
    )


@router.post("/logout")
async def logout(
    response: Response,
    current_user=Depends(get_current_user),
    app_db: AppDatabase = Depends(get_app_db),
    db_provider: DatabaseProvider = Depends(get_db_provider),
    session_cache: SessionCache = Depends(get_session_cache)
):
    """
    User logout endpoint.
    
    Clears auth cookie, updates logs, and closes user database connections.
    """
    # Clear token from cookie
    response.delete_cookie(
        key="access_token",
        secure=False,
        samesite="strict",
        httponly=True
    )
    
    await app_db.update_login_log(user_id=current_user.id)
    
    await db_provider.close_user_engines(current_user.id)

    session_cache.remove(current_user.id)

    return {"message": "Successfully logged out"}