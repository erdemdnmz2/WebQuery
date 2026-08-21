"""
Common Dependency Injection Functions
All routers use these functions to retrieve service instances from app.state.
"""
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select

from admin.services import AdminService
from app_database.app_database import AppDatabase
from app_database.models import User, UserDatabaseAssociation, Workspace
from authentication.services import get_current_user
from database_provider import DatabaseProvider
from notification import NotificationService
from query_execution.services import QueryService
from workspaces.exceptions import WorkspaceAccessDeniedError, WorkspaceNotFoundError
from workspaces.services import WorkspaceService


class AppContext:
    """
    Application context container that initializes and retains singletons
    of stateless services and database providers during application lifespan.
    """
    def __init__(self, app_db: AppDatabase, db_provider: DatabaseProvider):
        self.app_db = app_db
        self.db_provider = db_provider
        
        # Initialize stateless services
        self.notification_service = NotificationService()
        self.query_service = QueryService(
            database_provider=self.db_provider,
            app_db=self.app_db,
            notification_service=self.notification_service
        )
        self.workspace_service = WorkspaceService(app_db=self.app_db)
        self.admin_service = AdminService(app_db=self.app_db, db_provider=self.db_provider)


def get_context(request: Request) -> AppContext:
    """
    Returns the AppContext container from request app state.
    """
    return request.app.state.context


def get_app_db(context: AppContext = Depends(get_context)) -> AppDatabase:
    """
    Returns the AppDatabase instance from context.
    Usage: app_db: AppDatabase = Depends(get_app_db)
    """
    return context.app_db


def get_db_provider(context: AppContext = Depends(get_context)) -> DatabaseProvider:
    """
    Returns the DatabaseProvider instance from context.
    Usage: db_provider: DatabaseProvider = Depends(get_db_provider)
    """
    return context.db_provider


def get_query_service(context: AppContext = Depends(get_context)) -> QueryService:
    """
    Returns the QueryService instance from context.
    Usage: query_service: QueryService = Depends(get_query_service)
    """
    return context.query_service


def get_workspace_service(context: AppContext = Depends(get_context)) -> WorkspaceService:
    """
    Returns the WorkspaceService instance from context.
    Usage: workspace_service: WorkspaceService = Depends(get_workspace_service)
    """
    return context.workspace_service


def get_admin_service(context: AppContext = Depends(get_context)) -> AdminService:
    """
    Returns the AdminService instance from context.
    Usage: admin_service: AdminService = Depends(get_admin_service)
    """
    return context.admin_service


def get_notification_service(context: AppContext = Depends(get_context)) -> NotificationService:
    """
    Returns the NotificationService instance from context.
    Usage: notification_service: NotificationService = Depends(get_notification_service)    
    """
    return context.notification_service


async def admin_required(
    current_user: User = Depends(get_current_user),
    app_db: AppDatabase = Depends(get_app_db)
) -> User:
    """Dependency: ensures current_user is admin on at least one database."""
    if not current_user:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    
    async with app_db.get_app_db() as db:
        # User could have multiple roles separated by commas, check if 'ADMIN' is in any of them
        # But SQL 'like' or pulling all associations is safer.
        # Let's fetch all database associations for this user
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