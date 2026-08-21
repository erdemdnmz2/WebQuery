from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select

from app_database.app_database import AppDatabase
from app_database.models import User, UserDatabaseAssociation
from dependencies import get_app_db

router = APIRouter()

@router.get("/", response_class=FileResponse)
def homepage(current_user : User = Depends(get_current_user)):
    return FileResponse("templates/home.html")

@router.get("/index", response_class=FileResponse)
def index_page_direct(current_user : User = Depends(get_current_user)):
    return FileResponse("templates/index.html")

@router.get("/home", response_class=FileResponse)
def index_page(current_user : User = Depends(get_current_user)):
    return FileResponse("templates/index.html")

@router.get("/login", response_class=FileResponse)
def login_page():
    return FileResponse("templates/login.html")

@router.get("/register", response_class=FileResponse)
def register_page():
    return FileResponse("templates/register.html")

from authentication.services import get_current_user


@router.get("/admin", response_class=FileResponse)
async def admin(
    current_user: User = Depends(get_current_user),
    app_db: AppDatabase = Depends(get_app_db)
):
    async with app_db.get_app_db() as db:
        stmt = select(UserDatabaseAssociation).where(UserDatabaseAssociation.user_id == current_user.id)
        res = await db.execute(stmt)
        assocs = res.scalars().all()
        is_admin = False
        for assoc in assocs:
            roles = [r.strip().upper() for r in assoc.role.split(",")]
            if "ADMIN" in roles:
                is_admin = True
                break
                
    if not is_admin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin privileges required"
        )
    return FileResponse("templates/admin.html")