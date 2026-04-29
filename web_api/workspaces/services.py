"""
Workspace Service Layer
User workspace (saved query) management operations
"""
from app_database.models import QueryData, Workspace
from app_database.app_database import AppDatabase
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
from .schemas import WorkspaceInfo, WorkspaceCreate
from sqlalchemy.sql import select
from sqlalchemy.sql import text
from query_execution import config as query_config
from database_provider import DatabaseProvider
from session.session_cache import SessionCache
from app_database.models import User

class WorkspaceService:
    """
    Workspace CRUD operations service
    
    Manages users' operations of storing, editing, deleting,
    and listing queries in workspaces.
    
    Attributes:
        app_db: Application database instance
    """

    def __init__(self, app_db: AppDatabase):
        """
        Initializes WorkspaceService
        
        Args:
            app_db: AppDatabase instance
        """
        self.app_db = app_db

    async def create_workspace(self, db: AsyncSession, workspace_data: WorkspaceCreate, user_id: int):
        """
        Creates a new workspace.
        
        Args:
            db: Async database session
            workspace_data: Workspace creation schema
            user_id: ID of the user creating the workspace
        
        Returns:
            Dict: Result with workspace_id or error
        """
        try:
            new_query_data = QueryData(
                    user_id=user_id,
                    servername=workspace_data.servername,
                    database_name=workspace_data.database_name,
                    query=workspace_data.query,
                    uuid=str(uuid.uuid4()),
                    status="saved_in_workspace"
                )
            
            db.add(new_query_data)
            await db.flush()

            """Workspace creation operation"""
            workspace = Workspace(
                name=workspace_data.name,
                description=workspace_data.description,
                user_id=user_id,
                query_id=new_query_data.id
            )
            db.add(workspace)
            await db.commit()
            await db.refresh(workspace)
            return {"success": True, "workspace_id": workspace.id}
        except Exception as e:
            await db.rollback()
            print(f"Error creating workspace: {e}")
            return {"success": False, "error": str(e)}
        
    async def get_workspace_by_id(self, db: AsyncSession, user_id: int):
        """
        Retrieves all workspaces for the user.
        
        Args:
            db: Async database session
            user_id: ID of the user whose workspaces will be retrieved
        
        Returns:
            List[WorkspaceInfo]: List of workspaces (can be empty)
        """
        
        results = await db.execute(
            select(Workspace).where(Workspace.user_id == user_id)
        )
        workspaces = results.scalars().all()
        if not workspaces:
            return []

        query_ids = [ws.query_id for ws in workspaces]

        query_data_results = await db.execute(
            select(QueryData).where(QueryData.id.in_(query_ids))
        )
        query_data_map = {qd.id: qd for qd in query_data_results.scalars().all()}

        workspace_list = []
        for ws in workspaces:
            query_data = query_data_map.get(ws.query_id)
            if query_data:
                print(f"[DEBUG] Workspace {ws.id}: status={query_data.status}, show_results={getattr(ws, 'show_results', None)}")
                workspace_list.append(WorkspaceInfo(
                    id=ws.id,
                    name=ws.name,
                    description=ws.description,
                    query=query_data.query,
                    servername=query_data.servername,
                    database_name=query_data.database_name,
                    status=query_data.status,
                    show_results=getattr(ws, 'show_results', None),
                    owner_id=ws.user_id,
                    is_owner=True
                ))
        return workspace_list
    
    async def delete_workspace_by_id(self, workspace_id: int, db: AsyncSession):
        """
        Deletes workspace and related queryData.
        
        Args:
            workspace_id: ID of the workspace to delete
            db: Async database session
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            workspace_result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
            workspace = workspace_result.scalars().first()
            if not workspace:
                return False
            
            query_id = workspace.query_id
            
            await db.delete(workspace)
            
            if query_id:
                query_result = await db.execute(select(QueryData).where(QueryData.id == query_id))
                query_data = query_result.scalars().first()
                if query_data:
                    await db.delete(query_data)
            
            await db.commit()
            return True
        except Exception as e:
            await db.rollback()
            print(f"Error deleting workspace: {e}")
            return False
    
    async def update_workspace(self, db: AsyncSession, workspace_id: int, query: str = None, status: str = None):
        """
        Updates workspace query or status.
        
        Args:
            db: Async database session
            workspace_id: ID of the workspace to update
            query: New query (optional)
            status: New status (optional)
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            workspace_result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
            workspace = workspace_result.scalars().first()
            if not workspace:
                return False
            
            query_result = await db.execute(select(QueryData).where(QueryData.id == workspace.query_id))
            query_data = query_result.scalars().first()
            if not query_data:
                return False
            
            if query:
                query_data.query = query
            if status:
                query_data.status = status
            await db.commit()
            return True
        except Exception as e:
            await db.rollback()
            print(f"Error updating workspace: {e}")
            return False
    
    async def get_workspace_detail_by_id(self, db: AsyncSession, workspace_id: int, user_id: int):
        """
        Retrieves details of a specific workspace.
        
        Args:
            db: Async database session
            workspace_id: ID of the workspace to retrieve details for
            user_id: ID of the requesting user (for authorization check)
        
        Returns:
            Dict | None: Workspace details or None
        """
        workspace_result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
        workspace = workspace_result.scalars().first()
        if not workspace or workspace.user_id != user_id:
            return None
        query_result = await db.execute(select(QueryData).where(QueryData.id == workspace.query_id))
        query_data = query_result.scalars().first()
        if not query_data:
            return None
        return {
            "id": workspace.id,
            "name": workspace.name,
            "description": workspace.description,
            "query": query_data.query,
            "servername": query_data.servername,
            "database_name": query_data.database_name,
            "status": query_data.status,
            "show_results": getattr(workspace, 'show_results', None),
            "owner_id": workspace.user_id,
            "is_owner": True
        }

    async def execute_workspace(self, workspace_id: int, current_user: User, session_cache: SessionCache, db_provider: DatabaseProvider):
        """
        Executes a stored workspace query after enforcing approval rules.

        Args:
            workspace_id: ID of the workspace to execute
            current_user: Calling user
            session_cache: SessionCache instance
            db_provider: DatabaseProvider instance

        Returns:
            Dict: Execution result
        """
        # Session validation
        from authentication import config as auth_config
        try:
            if session_cache.is_valid(current_user.id, timeout_minutes=auth_config.SESSION_TIMEOUT):
                plain_pw = session_cache.get_password(current_user.id)
                current_user.password = plain_pw
            else:
                return {"response_type": "error", "data": [], "error": "Session expired"}
        except Exception:
            return {"response_type": "error", "data": [], "error": "Session password error"}

        # Load workspace and query
        async with self.app_db.get_app_db() as db:
            workspace_result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
            workspace = workspace_result.scalars().first()
            if not workspace:
                return {"response_type": "error", "data": [], "error": "Workspace not found"}

            query_result = await db.execute(select(QueryData).where(QueryData.id == workspace.query_id))
            query_data = query_result.scalars().first()
            if not query_data:
                return {"response_type": "error", "data": [], "error": "Query data not found"}
            # enforce approval
            if not workspace.show_results or query_data.status != "approved_with_results":
                return {"response_type": "error", "data": [], "error": "This workspace is not approved for execution"}

        log_id = None
        try:
            log_id = await self.app_db.create_log(user=current_user, query=query_data.query, machine_name=query_data.servername, approved_execution=True)

            async with db_provider.get_session(user=current_user, servername=query_data.servername, database_name=query_data.database_name) as session:
                sql_query = text(query_data.query)
                result = await session.execute(sql_query)
                rows = result.fetchmany(size=query_config.MAX_ROW_COUNT_LIMIT)
                row_count = len(rows)

                if row_count > query_config.MAX_ROW_COUNT_LIMIT:
                    rows = rows[:query_config.MAX_ROW_COUNT_LIMIT]
                    message = f"Truncated to MAX_ROW_COUNT_LIMIT ({query_config.MAX_ROW_COUNT_LIMIT})"
                else:
                    message = f"{row_count} rows affected"

                result_data = [dict(row._mapping) for row in rows]

            await self.app_db.update_log(log_id=log_id, successfull=True, row_count=row_count)

            return {"response_type": "data", "data": result_data, "message": message}

        except Exception as e:
            if log_id:
                await self.app_db.update_log(log_id=log_id, successfull=False, error=str(e))
            return {"response_type": "error", "data": [], "error": str(e)}