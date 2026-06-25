"""
Common Dependency Injection Functions
All routers use these functions to retrieve service instances from app.state.
"""
from fastapi import Request
from fastapi import Depends, HTTPException, status

from app_database.app_database import AppDatabase
from database_provider import DatabaseProvider
from authentication.services import get_current_user
from app_database.models import Workspace, User

from query_execution.services import QueryService
from workspaces.services import WorkspaceService
from workspaces.exceptions import WorkspaceNotFoundError, WorkspaceAccessDeniedError

def get_app_db(request: Request) -> AppDatabase:
    """
    Returns the AppDatabase instance.
    Usage: app_db: AppDatabase = Depends(get_app_db)
    """
    return request.app.state.app_db


def get_db_provider(request: Request) -> DatabaseProvider:
    """
    Returns the DatabaseProvider instance.
    Usage: db_provider: DatabaseProvider = Depends(get_db_provider)
    """
    return request.app.state.db_provider


# removed session cache and fernet dependencies as password caching is eliminated

def get_query_service(request: Request) -> QueryService:
    """
    Returns the QueryService instance.
    Usage: query_service: QueryService = Depends(get_query_service)
    """
    app_db = get_app_db(request)
    db_provider = get_db_provider(request)
    notification_service = get_notification_service(request)
    return QueryService(database_provider=db_provider, app_db=app_db, notification_service=notification_service)


def get_workspace_service(request: Request) -> WorkspaceService:
    """
    Returns the WorkspaceService instance.
    Usage: workspace_service: WorkspaceService = Depends(get_workspace_service)
    """
    app_db = get_app_db(request)
    return WorkspaceService(app_db=app_db)

from admin.services import AdminService

def get_admin_service(request: Request) -> AdminService:
    """
    Returns the AdminService instance.
    Usage: admin_service: AdminService = Depends(get_admin_service)
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
            raise WorkspaceNotFoundError("Workspace not found")
        if ws.user_id != current_user.id:
            raise WorkspaceAccessDeniedError("You don't own this workspace.")
        return ws


from notification import NotificationService

def get_notification_service(request: Request) -> NotificationService:
    """
    Returns the NotificationService instance.
    Usage: notification_service: NotificationService = Depends(get_notification_service)    
    """
    return NotificationService()