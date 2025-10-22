from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from authentication.services import get_current_user
from app_database.models import User

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

@router.get("/admin", response_class=FileResponse)
def admin(current_user: User = Depends(get_current_user)):
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin privileges required"
        )
    return FileResponse("templates/admin.html")