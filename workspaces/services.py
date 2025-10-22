"""
Workspace Service Layer
Kullanıcı workspace (kaydedilmiş query) yönetim işlemleri
"""
from app_database.models import queryData, Workspace
from app_database.app_database import AppDatabase
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
from .schemas import WorkspaceInfo, WorkspaceCreate
from sqlalchemy.sql import select

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