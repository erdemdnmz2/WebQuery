"""
Admin Service Layer
Riskli query'lerin admin onayı ve yönetimi işlemleri
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import select, text
from app_database.models import queryData, Workspace, User
from app_database.app_database import AppDatabase
from database_provider import DatabaseProvider
from .schemas import *

class AdminService:
    """
    Admin query onay ve yönetim servisi
    
    Riskli olarak işaretlenen query'lerin admin tarafından onaylanması,
    reddedilmesi veya çalıştırılması işlemlerini yönetir.
    
    Attributes:
        app_db: Uygulama veritabanı instance
        db_provider: Veritabanı bağlantı sağlayıcı
    """
    
    def __init__(self, app_db: AppDatabase, db_provider: DatabaseProvider):
        """
        AdminService'i başlatır
        
        Args:
            app_db: AppDatabase instance
            db_provider: DatabaseProvider instance
        """
        self.app_db = app_db
        self.db_provider = db_provider

    async def get_workspaces_for_approval(self):
        """
        Admin onayı bekleyen workspace'leri getirir
        
        Returns:
            List[AdminApprovals]: Onay bekleyen query listesi
            
        Note:
            Status = "waiting_for_approval" olan kayıtları getirir
            Her kayıt için user, workspace ve query bilgileri birleştirilir
        """
        result_list = []
        try:
            async with self.app_db.get_app_db() as db:
                results = await db.execute(select(queryData).where(queryData.status == "waiting_for_approval"))
                queries = results.scalars().all()
                if queries:
                    for query in queries:
                       
                        workspace_result = await db.execute(
                            select(Workspace).where(Workspace.query_id == query.id)
                        )
                        workspace = workspace_result.scalars().first()

                        user = await db.get(User, query.user_id)
                        
                        if workspace and user:
                            data = AdminApprovals(
                                user_id=query.user_id,
                                workspace_id=workspace.id,
                                username = user.username,
                                query= query.query,
                                database=query.database_name,
                                status= query.status,
                                risk_type=query.risk_type,
                                servername=query.servername
                            )

                            result_list.append(data)
            return result_list
        except  Exception as e:
            print(f"Error: {str(e)}")
            return []
        
    async def approve_query_by_workspace_id(self, workspace_id: int):
        """
        Query'yi onaylar ve çalıştırır
        
        İş Akışı:
            1. Workspace ve ilişkili query'yi bul
            2. User bilgilerini al
            3. Query'yi hedef veritabanında çalıştır
            4. Başarılıysa: status = "approved_and_executed"
            5. Başarısızsa: status = "approval_execution_failed"
            6. Sonuçları döndür
        
        Args:
            workspace_id: Onaylanacak workspace ID'si
        
        Returns:
            Dict: {
                "success": bool,
                "data": List[Dict] (query sonuçları, başarılıysa),
                "row_count": int (başarılıysa),
                "query": str (başarılıysa),
                "database": str (başarılıysa),
                "servername": str (başarılıysa),
                "error": str (başarısızsa)
            }
        
        Note:
            - Query çalıştırılır ve sonucu döndürülür
            - Başarısız olsa bile status güncellenir
            - Workspace description'a durum mesajı yazılır
        """
        async with self.app_db.get_app_db() as db:
            workspace = await db.get(Workspace, workspace_id)
            if not workspace:
                return {"success": False, "error": "Workspace not found"}
                    
            query_data = await db.get(queryData, workspace.query_id)
            if not query_data:
                return {"success": False, "error": "Query data not found"}
                    
            user = await db.get(User, query_data.user_id)
            if not user:
                return {"success": False, "error": "User not found"}

            try:
                async with self.db_provider.get_session(user, query_data.servername, query_data.database_name) as session:
                    sql_query = text(query_data.query)
                    result = await session.execute(sql_query)
                    rows = result.fetchall()
                    row_count = len(rows)

                    result_data = [dict(row._mapping) for row in rows]

                workspace_to_update = await db.get(Workspace, workspace_id)
                query_data_to_update = await db.get(queryData, query_data.id)
                    
                if query_data_to_update:
                    query_data_to_update.status = "approved_and_executed"
                if workspace_to_update:
                    workspace_to_update.description = f"Admin tarafından onaylandı ve çalıştırıldı - {row_count} satır etkilendi"
                    
                await db.commit()
                
                return {
                    "success": True,
                    "data": result_data,
                    "row_count": row_count,
                    "query": query_data.query,
                    "database": query_data.database_name,
                    "servername": query_data.servername
                }
                
            except Exception as e:
                try:
                    workspace_to_update = await db.get(Workspace, workspace_id)
                    query_data_to_update = await db.get(queryData, query_data.id)
                        
                    if query_data_to_update:
                        query_data_to_update.status = "approval_execution_failed"
                    if workspace_to_update:
                        workspace_to_update.description = f"Admin onayladı ancak çalıştırma başarısız: {str(e)}"
                        
                    await db.commit()
                except Exception as db_error:
                        print(f"Durum güncellenirken hata: {db_error}")
                
                print(f"Sorgu onaylanırken hata: {e}")
                return {"success": False, "error": str(e)}

    async def reject_query_by_workspace_id(self, workspace_id: int):
        """
        Query'yi reddeder
        
        Args:
            workspace_id: Reddedilecek workspace ID'si
        
        Returns:
            Dict: {
                "success": bool,
                "error": str (başarısızsa)
            }
        
        Note:
            - Query status = "rejected" olarak güncellenir
            - Workspace description'a red mesajı yazılır
            - Query çalıştırılmaz
        """
        async with self.app_db.get_app_db() as db:
            try:
                workspace = await db.get(Workspace, workspace_id)
                if not workspace:
                    return {"success": False, "error": "Workspace not found"}
                    
                query_data = await db.get(queryData, workspace.query_id)
                if not query_data:
                    return {"success": False, "error": "Query data not found"}
                
                query_data.status = "rejected"
                workspace.description = "Admin tarafından reddedildi"
                
                await db.commit()
                return {"success": True}
                
            except Exception as e:
                await db.rollback()
                print(f"Error rejecting query: {e}")
                return {"success": False, "error": str(e)}
