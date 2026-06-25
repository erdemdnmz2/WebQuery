"""
Authentication Router Module
FastAPI router for user login, registration, logout, and self-information.
Strictly typed and documented.
"""
from fastapi import APIRouter, HTTPException, Response, Request, Depends
import os
from typing import Any
from common.limiter import limiter

from authentication.exceptions import UserAlreadyExistsError

from authentication import config
from authentication import schemas
from authentication.services import create_access_token, get_current_user
from dependencies import get_app_db, get_db_provider
from app_database.app_database import AppDatabase
from database_provider import DatabaseProvider
from app_database.models import User

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
        from sqlalchemy.future import select
        
        result = await db.execute(select(User).where(User.email == user.email))
        authenticated_user: User | None = result.scalars().first()
        
        if not authenticated_user or not authenticated_user.check_password(user.password):
            raise HTTPException(status_code=400, detail="Invalid email or password")
        
        user_id: int = int(authenticated_user.id)
        
        # Create JWT token
        user_to_login: dict[str, str] = {"sub": str(user_id)}
        token: str = create_access_token(user_to_login)
        
        response.set_cookie(
            key="access_token",
            value=token,
            secure=os.getenv("COOKIE_SECURE", "False").lower() == "true",
            samesite="strict",
            httponly=True,
            max_age=config.COOKIE_TOKEN_EXPIRE_MINUTES
        )
        
        client_ip: str = request.client.host if request.client else "unknown"
        await app_db.create_login_log(user_id=user_id, client_ip=client_ip)
        
        return {"access_token": token}


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
        from sqlalchemy.future import select
        
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
            raise HTTPException(status_code=500, detail=f"Database error during registration: {str(e)}")
        
        return {
            "success": True,
            "message": "Registration successful! Redirecting to login page..."
        }


@router.get("/me", response_model=schemas.User)
async def read_users_me(current_user: User = Depends(get_current_user)) -> schemas.User:
    """
    Returns current authenticated user information.
    
    Args:
        current_user: The authenticated user instance.
        
    Returns:
        schemas.User: The user details schema.
    """
    return schemas.User(
        username=current_user.username,
        is_admin=current_user.is_admin if current_user.is_admin is not None else False
    )


@router.post("/logout")
async def logout(
    response: Response,
    current_user: User = Depends(get_current_user),
    app_db: AppDatabase = Depends(get_app_db),
    db_provider: DatabaseProvider = Depends(get_db_provider)
) -> dict[str, str]:
    """
    User logout endpoint.
    Clears auth cookie, updates logout logs, and closes user target database engines.
    
    Args:
        response: The FastAPI response object.
        current_user: The authenticated user instance.
        app_db: The application database manager instance.
        db_provider: The database provider instance.
        
    Returns:
        dict[str, str]: A dictionary with success status.
    """
    # Clear token from cookie
    response.delete_cookie(
        key="access_token",
        secure=os.getenv("COOKIE_SECURE", "False").lower() == "true",
        samesite="strict",
        httponly=True
    )
    
    await app_db.update_login_log(user_id=current_user.id)
    await db_provider.close_user_engines(current_user.id)

    return {"message": "Successfully logged out"}