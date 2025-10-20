from app_database.models import queryData, Workspace
from app_database.app_database import AppDatabase
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
from schemas import WorkspaceInfo
from sqlalchemy.sql import select

class WorkspaceService:

    def __init__(self, app_db: AppDatabase):
        self.app_db = app_db

    async def create_workspace(self, db: AsyncSession, workspace_data: WorkspaceInfo, user_id: int):
        try:
            new_query_data = queryData(
                    user_id=user_id,
                    servername=workspace_data.servername,
                    database_name=workspace_data.database_name,
                    query=workspace_data.query,
                    uuid=str(uuid.uuid4()),
                    status="saved_in_workspace"
                )
            
            db.add(new_query_data)
            await db.flush()

            """Workspace oluşturma işlemi"""
            workspace = Workspace(
                name=workspace_data.get("name"),
                description=workspace_data.get("description"),
                user_id=user_id
            )
            db.add(workspace)
            await db.commit()
            await db.refresh(workspace)
            return {"success": True, "workspace_id": workspace.id}
        except Exception as e:
            db.rollback()
            print(f"Error creating workspace: {e}")
            return {"success": False, "error": str(e)}
        
    async def get_workspace_by_id(db: AsyncSession, user_id: int):
        
        results = await db.execute(
            select(Workspace).where(Workspace.user_id == user_id)
        )
        workspaces = results.scalars().all()
        if not workspaces:
            return []

        query_ids = [ws.query_id for ws in workspaces]

        query_data_results = await db.execute(
            select(queryData).where(queryData.id.in_(query_ids))
        )
        query_data_map = {qd.id: qd for qd in query_data_results.scalars().all()}

        workspace_list = []
        for ws in workspaces:
            query_data = query_data_map.get(ws.query_id)
            if query_data:
                workspace_list.append(WorkspaceInfo(
                    id=ws.id,
                    name=ws.name,
                    description=ws.description,
                    query=query_data.query,
                    servername=query_data.servername,
                    database_name=query_data.database_name,
                    status=query_data.status
                ))
        return workspace_list
    
    async def delete_workspace_by_id(workspace_id: int, db: AsyncSession):
        try:
            workspace = await db.get(Workspace, workspace_id)
            if not workspace:
                return False
            
            query_id = workspace.query_id
            
            await db.delete(workspace)
            
            if query_id:
                query_data = await db.get(queryData, query_id)
                if query_data:
                    await db.delete(query_data)
            
            await db.commit()
            return True
        except Exception as e:
            await db.rollback()
            print(f"Error deleting workspace: {e}")
            return False
    
    async def update_workspace(self, db: AsyncSession, workspace_id: int, query: str = None, status: str = None):
        try:
            workspace = await db.get(Workspace, workspace_id)
            if not workspace:
                return False
            
            query_data = await db.get(queryData, workspace.query_id)
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
        workspace = await db.get(Workspace, workspace_id)
        if not workspace or workspace.user_id != user_id:
            return None
        query_data = await db.get(queryData, workspace.query_id)
        if not query_data:
            return None
        return {
            "id": workspace.id,
            "name": workspace.name,
            "description": workspace.description,
            "query": query_data.query,
            "servername": query_data.servername,
            "database_name": query_data.database_name,
            "status": query_data.status
        }