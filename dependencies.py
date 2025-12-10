"""
Ortak Dependency Injection Fonksiyonları
Tüm router'lar bu fonksiyonları kullanarak app.state'ten instance'ları alır
"""
from fastapi import Request
from fastapi import Depends, HTTPException, status
from cryptography.fernet import Fernet

from app_database.app_database import AppDatabase
from database_provider import DatabaseProvider
from authentication.services import get_current_user
from app_database.models import Workspace, QueryData, User

from query_execution.services import QueryService
from workspaces.services import WorkspaceService

def get_app_db(request: Request) -> AppDatabase:
    """
    AppDatabase instance'ını döndürür.
    Kullanım: app_db: AppDatabase = Depends(get_app_db)
    """
    return request.app.state.app_db


def get_db_provider(request: Request) -> DatabaseProvider:
    """
    DatabaseProvider instance'ını döndürür.
    Kullanım: db_provider: DatabaseProvider = Depends(get_db_provider)
    """
    return request.app.state.db_provider


from session.session_cache import SessionCache

def get_session_cache(request: Request) -> SessionCache:
    """
    SessionCache instance'ını döndürür (kullanıcı şifrelerini geçici saklar).
    Kullanım: session_cache: SessionCache = Depends(get_session_cache)
    """
    return request.app.state.session_cache


def get_fernet(request: Request) -> Fernet:
    """
    Fernet şifreleme instance'ını döndürür.
    Kullanım: fernet: Fernet = Depends(get_fernet)
    """
    return request.app.state.fernet

def get_query_service(request: Request) -> QueryService:
    """
    QueryService instance'ını döndürür.
    Kullanım: query_service: QueryService = Depends(get_query_service)
    """
    app_db = get_app_db(request)
    db_provider = get_db_provider(request)
    notification_service = get_notification_service(request)
    return QueryService(database_provider=db_provider, app_db=app_db, notification_service=notification_service)

from workspaces.services import WorkspaceService

def get_workspace_service(request: Request) -> WorkspaceService:
    """
    WorkspaceService instance'ını döndürür.
    Kullanım: workspace_service: WorkspaceService = Depends(get_workspace_service)
    """
    app_db = get_app_db(request)
    return WorkspaceService(app_db=app_db)

from admin.services import AdminService

def get_admin_service(request: Request) -> AdminService:
    """
    AdminService instance'ını döndürür.
    Kullanım: admin_service: AdminService = Depends(get_admin_service)
    """
    app_db = get_app_db(request)
    db_provider = get_db_provider(request)
    return AdminService(app_db=app_db, db_provider=db_provider)


async def admin_required(current_user: User = Depends(get_current_user)) -> User:
    """Dependency: ensures current_user is admin."""
    if not current_user or not getattr(current_user, "is_admin", False):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user


async def ensure_owner(workspace_id: int,
                       current_user: User = Depends(get_current_user),
                       app_db: AppDatabase = Depends(get_app_db)) -> Workspace:
    """Dependency: ensures the current_user is the owner of the workspace. Returns the Workspace."""
    async with app_db.get_app_db() as db:
        ws = await db.get(Workspace, workspace_id)
        if not ws:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
        if ws.user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You don't own this workspace.")
        return ws


from notification import NotificationService

def get_notification_service(request: Request) -> NotificationService:
    """
    NotificationService instance'ını döndürür.
    Kullanım: notification_service: NotificationService = Depends(get_notification_service)    
    """
    return NotificationService()