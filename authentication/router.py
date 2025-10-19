from fastapi import APIRouter, HTTPException, Response, Request, Depends
from slowapi import Limiter
from slowapi.util import get_remote_address
from datetime import datetime
from cryptography.fernet import Fernet

import config
import schemas
import crud
import auth
from database_provider import get_app_db, add_user_to_cache, engine_cache, session_cache
from crud import create_login_log

# Session encryption setup
session_key = Fernet.generate_key()
f = Fernet(session_key)

limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/api/auth/")

@router.post("/login", response_model=schemas.Token)
@limiter.limit(config.RATE_LIMITER)
async def login(user: schemas.UserLogin, response: Response, request: Request):
    async with get_app_db() as db:
        authenticated_user = await crud.authenticate_user(db, user.email, user.password)
    
        if not authenticated_user:
            raise HTTPException(status_code=400, detail="User not found")
        user_id = int(authenticated_user.id)
        username = str(authenticated_user.username)
        user_to_login = {"sub": str(user_id)}
        token = auth.create_access_token(user_to_login)

        response.set_cookie(
            key="access_token",
            value=token,
            secure=False,
            samesite="strict", 
            httponly=True,
            max_age=config.COOKIE_TOKEN_EXPIRE_MINUTES
        )
        client_ip = request.client.host
        await create_login_log(db=db, user_id=user_id, client_ip=client_ip)
        sub_dict = {
            "user_password": f.encrypt(user.password.encode()),
            "addition_date": datetime.now()
        }
        session_cache[user_id] = sub_dict

        if user_id not in engine_cache:
            await add_user_to_cache(
                user_id=user_id,
                username=username,
                password=user.password 
            )

        return {"access_token": token}
    
@router.post("/register")
@limiter.limit(config.RATE_LIMITER)        
async def register(user: schemas.UserCreate, response: Response, request: Request):
    async with get_app_db() as db:     
        if await crud.get_user_by_email(db, user.email):
            raise HTTPException(status_code=400, detail="Email already registered")
        
        register_result = await crud.create_user(db, user)
        
        if register_result["success"]:
            return register_result
        else:
            raise HTTPException(status_code=400, detail="User could not be created")
        
@router.get("/me", response_model=schemas.User)
async def read_users_me(current_user = Depends(get_current_user)):
    return schemas.User(
        username=current_user.username,
        is_admin=current_user.is_admin
    )