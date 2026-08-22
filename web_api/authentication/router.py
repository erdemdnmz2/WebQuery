"""
Authentication Router Module
FastAPI router for user login, registration, logout, and self-information.
Strictly typed and documented.
"""
import os
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from jose import jwt
from sqlalchemy.future import select

from app_database.app_database import AppDatabase
from app_database.models import User, UserDatabaseAssociation
from authentication import config, schemas, sessions
from authentication.exceptions import UserAlreadyExistsError
from authentication.services import get_current_user
from common.limiter import limiter
from common.roles import any_admin
from database_provider import DatabaseProvider
from dependencies import get_app_db, get_db_provider

router = APIRouter(prefix="/api")

# Using centralized limiter


@router.post("/login", response_model=schemas.Token)
@limiter.limit(config.RATE_LIMITER)
async def login(
    user: schemas.UserLogin,
    response: Response,
    request: Request,
    app_db: AppDatabase = Depends(get_app_db)
) -> dict[str, str]:
    """
    User login endpoint.
    Verifies credentials, creates JWT token, and writes login logs.
    
    Args:
        user: The user login credentials payload.
        response: The FastAPI response object (used to set auth cookies).
        request: The FastAPI request object (used for client IP logging).
        app_db: The application database manager instance.
        
    Returns:
        dict[str, str]: The access token response.
    """
    async with app_db.get_app_db() as db:
        result = await db.execute(select(User).where(User.email == user.email))
        authenticated_user: User | None = result.scalars().first()
        
        if not authenticated_user or not authenticated_user.check_password(user.password):
            raise HTTPException(status_code=400, detail="Invalid email or password")
        
        user_id: int = int(authenticated_user.id)
        
        client_ip: str = request.client.host if request.client else "unknown"
        session_id, refresh_token = await sessions.create_session(
            app_db, user_id, client_ip, request.headers.get("user-agent")
        )
        token = sessions.mint_access(user_id, session_id)
        
        response.set_cookie(
            key="access_token",
            value=token,
            secure=os.getenv("COOKIE_SECURE", "False").lower() == "true",
            samesite="strict",
            httponly=True,
            max_age=config.COOKIE_TOKEN_EXPIRE_MINUTES * 60,
            path="/",
        )
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            secure=os.getenv("COOKIE_SECURE", "False").lower() == "true",
            samesite="strict",
            httponly=True,
            max_age=sessions.REFRESH_TTL_HOURS * 3600,
            path="/api",
        )
        await app_db.create_login_log(user_id=user_id, client_ip=client_ip)
        
        return {"access_token": token}


@router.post("/refresh")
async def refresh_session(
    request: Request,
    response: Response,
    app_db: AppDatabase = Depends(get_app_db),
) -> dict[str, bool]:
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="Refresh token yok")

    rotated = await sessions.rotate_refresh(app_db, token)
    if rotated is None:
        raise HTTPException(status_code=401, detail="Oturum süresi doldu")
    if rotated.get("reuse"):
        raise HTTPException(status_code=401, detail="Güvenlik nedeniyle oturum sonlandırıldı. Tekrar giriş yapın.")

    async with app_db.get_app_db() as db:
        user = await db.get(User, rotated["user_id"])
    if user is None or not getattr(user, "is_active", True):
        await sessions.revoke_session(app_db, rotated["session_id"], "hesap devre dışı")
        raise HTTPException(status_code=401, detail="Hesabınız devre dışı bırakılmış")

    access = sessions.mint_access(rotated["user_id"], rotated["session_id"])
    response.set_cookie(
        key="access_token", value=access, httponly=True, samesite="strict",
        secure=os.getenv("COOKIE_SECURE", "False").lower() == "true",
        max_age=sessions.ACCESS_TTL_MINUTES * 60, path="/",
    )
    response.set_cookie(
        key="refresh_token", value=rotated["refresh_token"], httponly=True,
        samesite="strict", secure=os.getenv("COOKIE_SECURE", "False").lower() == "true",
        max_age=sessions.REFRESH_TTL_HOURS * 3600, path="/api",
    )
    return {"ok": True}


@router.post("/register")
@limiter.limit(config.RATE_LIMITER)
async def register(
    user: schemas.UserCreate,
    response: Response,
    request: Request,
    app_db: AppDatabase = Depends(get_app_db)
) -> dict[str, Any]:
    """
    New user registration endpoint.
    Registers a new user if the email is not already taken.
    
    Args:
        user: The user registration details payload.
        response: The FastAPI response object.
        request: The FastAPI request object.
        app_db: The application database manager instance.
        
    Returns:
        dict[str, any]: A dictionary indicating success or failure.
    """
    async with app_db.get_app_db() as db:
        result = await db.execute(select(User).where(User.email == user.email))
        existing_user: User | None = result.scalars().first()
        
        if existing_user:
            raise UserAlreadyExistsError("Email already registered")
        
        new_user: User = User(
            username=user.username,
            email=user.email
        )
        try:
            new_user.set_password(user.password)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        db.add(new_user)
        try:
            await db.commit()
            await db.refresh(new_user)
        except Exception as e:
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"Database error during registration: {e!s}")
        
        return {
            "success": True,
            "message": "Registration successful! Redirecting to login page..."
        }


@router.get("/me", response_model=schemas.User)
async def read_users_me(
    current_user: User = Depends(get_current_user),
    app_db: AppDatabase = Depends(get_app_db)
) -> schemas.User:
    """
    Returns current authenticated user information.
    
    Args:
        current_user: The authenticated user instance.
        app_db: The app database manager.
        
    Returns:
        schemas.User: The user details schema.
    """
    async with app_db.get_app_db() as db:
        stmt = select(UserDatabaseAssociation).where(UserDatabaseAssociation.user_id == current_user.id)
        res = await db.execute(stmt)
        assocs = res.scalars().all()
        is_admin = any_admin(assocs)

    return schemas.User(
        username=current_user.username,
        is_admin=is_admin
    )


@router.post("/logout")
async def logout(
    response: Response,
    request: Request,
    current_user: User = Depends(get_current_user),
    app_db: AppDatabase = Depends(get_app_db),
    db_provider: DatabaseProvider = Depends(get_db_provider)
) -> dict[str, str]:
    """
    User logout endpoint.
    Clears auth cookie, updates logout logs, and closes user target database engines.
    
    Args:
        response: The FastAPI response object.
        request: The FastAPI request object.
        current_user: The authenticated user instance.
        app_db: The application database manager instance.
        db_provider: The database provider instance.
        
    Returns:
        dict[str, str]: A dictionary with success status.
    """
    # Extract and blacklist the token if present
    token = request.cookies.get("access_token")
    if token:
        try:
            payload = jwt.decode(token, config.SECRET_KEY, algorithms=[config.ALGORITHM])
            jti = payload.get("jti")
            exp = payload.get("exp")
            if jti and exp:
                expires_at = datetime.fromtimestamp(exp, tz=timezone.utc)
                await app_db.blacklist_token(jti=jti, expires_at=expires_at)
            if payload.get("sid"):
                await sessions.revoke_session(app_db, int(payload["sid"]), "logout")
        except Exception as e:
            print(f"Error blacklisting token on logout: {e}")

    # Clear token from cookie
    response.delete_cookie(
        key="access_token",
        secure=os.getenv("COOKIE_SECURE", "False").lower() == "true",
        samesite="strict",
        httponly=True
    )
    response.delete_cookie(
        key="refresh_token",
        secure=os.getenv("COOKIE_SECURE", "False").lower() == "true",
        samesite="strict",
        httponly=True,
        path="/api",
    )
    
    await app_db.update_login_log(user_id=current_user.id)
    await db_provider.close_user_engines(current_user.id)

    return {"message": "Successfully logged out"}
