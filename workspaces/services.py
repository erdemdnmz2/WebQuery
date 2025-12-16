"""
Workspace Service Layer
Kullanıcı workspace (kaydedilmiş query) yönetim işlemleri
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
    Workspace CRUD işlemleri servisi
    
    Kullanıcıların query'lerini workspace'lerde saklaması, düzenlemesi,
    silmesi ve listelemesi işlemlerini yönetir.
    
    Attributes:
        app_db: Uygulama veritabanı instance
    """

    def __init__(self, app_db: AppDatabase):
        """
        WorkspaceService'i başlatır
        
        Args:
            app_db: AppDatabase instance
        """
        self.app_db = app_db

    async def create_workspace(self, db: AsyncSession, workspace_data: WorkspaceCreate, user_id: int):
        """
        Yeni workspace oluşturur
        
        İş Akışı:
            1. queryData kaydı oluştur (UUID ile)
            2. Workspace kaydı oluştur (queryData'ya bağlı)
            3. İki tabloyu da commit et
        
        Args:
            db: Async database session
            workspace_data: Workspace oluşturma şeması
            user_id: Workspace'i oluşturan kullanıcı ID'si
        
        Returns:
            Dict: {
                "success": bool,
                "workspace_id": int (başarılıysa),
                "error": str (başarısızsa)
            }
        
        Note:
            - Her workspace bir queryData kaydına bağlıdır (1:1)
            - Status: "saved_in_workspace"
            - UUID otomatik oluşturulur
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

            """Workspace oluşturma işlemi"""
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
        Kullanıcının tüm workspace'lerini getirir
        
        İş Akışı:
            1. User'a ait workspace'leri bul
            2. İlişkili queryData kayıtlarını getir (join)
            3. WorkspaceInfo DTO'larını oluştur
        
        Args:
            db: Async database session
            user_id: Workspace'leri getirilecek kullanıcı ID'si
        
        Returns:
            List[WorkspaceInfo]: Workspace listesi (boş liste olabilir)
        
        Note:
            queryData bulunamazsa o workspace atlanır
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
        Workspace'i ve ilişkili queryData'yı siler
        
        Args:
            workspace_id: Silinecek workspace ID'si
            db: Async database session
        
        Returns:
            bool: Başarılı ise True, değilse False
        
        Note:
            - Workspace ve queryData cascade delete (her ikisi de silinir)
            - Workspace bulunamazsa False döner
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
        Workspace'in query veya status'ünü günceller
        
        Args:
            db: Async database session
            workspace_id: Güncellenecek workspace ID'si
            query: Yeni query (opsiyonel)
            status: Yeni status (opsiyonel, ör: "waiting_for_approval")
        
        Returns:
            bool: Başarılı ise True, değilse False
        
        Note:
            - queryData tablosunu günceller (workspace değil)
            - En az bir parametre verilmelidir
            - Workspace veya queryData bulunamazsa False döner
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
        Belirli bir workspace'in detaylarını getirir
        
        Args:
            db: Async database session
            workspace_id: Detayı getirilecek workspace ID'si
            user_id: İstek yapan kullanıcı ID'si (yetki kontrolü için)
        
        Returns:
            Dict | None: Workspace detayları veya None (bulunamazsa/yetkisizse)
        
        Note:
            - Workspace sahibi kontrolü yapar (user_id eşleşmeli)
            - Workspace veya queryData bulunamazsa None döner
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
        Execute a stored workspace query after enforcing workspace-level approval rules.

        Args:
            workspace_id: ID of the workspace to execute
            current_user: calling user (must have valid session in session_cache)
            session_cache: SessionCache instance to validate session and retrieve password
            db_provider: DatabaseProvider to open a session against target DB

        Returns:
            Dict: same shape as QueryService.execute_query (response_type, data, message, error)
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

        # Execute using db_provider with the user's credentials
        log_id = None
        try:
            # Mark this log as an approved execution (user runs an admin-approved workspace)
            log = await self.app_db.create_log(user=current_user, query=query_data.query, machine_name=query_data.servername, approved_execution=True)
            log_id = log.id

            async with db_provider.get_session(user=current_user, servername=query_data.servername, database_name=query_data.database_name) as session:
                sql_query = text(query_data.query)
                result = await session.execute(sql_query)
                # fetch up to MAX_ROW_COUNT_LIMIT
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