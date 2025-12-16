"""
Admin Service Layer
Riskli query'lerin admin onayı ve yönetimi işlemleri
"""
from sqlalchemy.sql import select, text
from app_database.models import QueryData, Workspace, User
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
                results = await db.execute(select(QueryData).where(QueryData.status == "waiting_for_approval"))
                queries = results.scalars().all()
                if queries:
                    for query in queries:
                       
                        workspace_result = await db.execute(
                            select(Workspace).where(Workspace.query_id == query.id)
                        )
                        workspace = workspace_result.scalars().first()

                        user_result = await db.execute(select(User).where(User.id == query.user_id))
                        user = user_result.scalars().first()
                        
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
        
    async def execute_for_preview(self, workspace_id: int, admin_user: User):
        """
        Admin için query'yi çalıştırır ve önizler
        
        Henüz ONAYLANMAZ, sadece sonuçları döndürür.
        Query execution loglama yapılır (admin user ile).
        
        İş Akışı:
            1. Workspace ve ilişkili query'yi bul
            2. User bilgilerini al
            3. Query'yi hedef veritabanında çalıştır (MAX_ROW_COUNT_LIMIT ile)
            4. Sonuçları döndür
        
        Args:
            workspace_id: Preview edilecek workspace ID'si
            admin_user: Preview yapan admin kullanıcı
        
        Returns:
            Dict: {
                "success": bool,
                "data": List[Dict] (query sonuçları),
                "row_count": int,
                "query": str,
                "database": str,
                "servername": str,
                "error": str (başarısızsa)
            }
        
        Note:
            - Query çalıştırılır ama loglama yapılmaz (preview)
            - MAX_ROW_COUNT_LIMIT kontrolü uygulanır
            - Status değiştirilmez
        """
        log_id = None
        
        async with self.app_db.get_app_db() as db:
            workspace_result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
            workspace = workspace_result.scalars().first()
            if not workspace:
                return {"success": False, "error": "Workspace not found"}
                    
            query_result = await db.execute(select(QueryData).where(QueryData.id == workspace.query_id))
            query_data = query_result.scalars().first()
            if not query_data:
                return {"success": False, "error": "Query data not found"}
                    
            user_result = await db.execute(select(User).where(User.id == admin_user.id))
            user = user_result.scalars().first()
            if not user:
                return {"success": False, "error": "User not found"}
            
            query_text = query_data.query
            servername = query_data.servername
            database_name = query_data.database_name
        
        try:
            log_id = await self.app_db.create_log(
                user=admin_user, 
                query=query_text, 
                machine_name=servername
            )
            
            async with self.db_provider.get_session(user, servername, database_name) as session:
                sql_query = text(query_text)
                result = await session.execute(sql_query)
                rows = result.fetchall()
                row_count = len(rows)
                
                from query_execution import config
                if row_count > config.MAX_ROW_COUNT_LIMIT:
                    rows = rows[:config.MAX_ROW_COUNT_LIMIT]
                    row_count = config.MAX_ROW_COUNT_LIMIT

                result_data = [dict(row._mapping) for row in rows]
            
            await self.app_db.update_log(
                log_id=log_id,
                successfull=True,
                row_count=row_count
            )

            columns = list(result_data[0].keys()) if result_data else []
            message = None
            from query_execution import config
            if row_count > 0 and row_count == config.MAX_ROW_COUNT_LIMIT:
                message = f"Truncated to MAX_ROW_COUNT_LIMIT ({config.MAX_ROW_COUNT_LIMIT})"

            return {
                "response_type": "data",
                "data": result_data,
                "columns": columns,
                "row_count": row_count,
                "message": message,
                "error": None
            }
        except Exception as e:
            if log_id:
                await self.app_db.update_log(
                    log_id=log_id,
                    successfull=False,
                    error=str(e)
                )

            print(f"Query preview failed: {e}")
            return {
                "response_type": "error",
                "data": [],
                "columns": [],
                "row_count": 0,
                "message": None,
                "error": str(e)
            }

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
                workspace_result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
                workspace = workspace_result.scalars().first()
                if not workspace:
                    return {"success": False, "error": "Workspace not found"}
                    
                query_result = await db.execute(select(QueryData).where(QueryData.id == workspace.query_id))
                query_data = query_result.scalars().first()
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
            
    async def approve(self, workspace_id: int, show_results: bool):
        """
        Query'yi onaylar (EXECUTE ETMEZ, sadece işaretler)
        
        Args:
            workspace_id: Onaylanacak workspace ID'si
            show_results: 
                - TRUE → Workspace "executable" olarak işaretlenir
                - FALSE → Workspace "approved but not executable"
        
        Returns:
            Dict: {
                "success": bool,
                "status": str,
                "message": str,
                "error": str (başarısızsa)
            }
        
        Note:
            - Query ÇALIŞTIRILMAZ
            - Sadece status + show_results güncellenir
            - Admin daha önce execute_for_preview ile sonuçları görmüş olmalı
        """
        async with self.app_db.get_app_db() as db:
            try:
                workspace_result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
                workspace = workspace_result.scalars().first()
                if not workspace:
                    return {"success": False, "error": "Workspace not found"}
                
                query_result = await db.execute(select(QueryData).where(QueryData.id == workspace.query_id))
                query_data = query_result.scalars().first()
                if not query_data:
                    return {"success": False, "error": "Query data not found"}
                
                if show_results:
                    query_data.status = "approved_with_results"
                    workspace.show_results = True
                    workspace.description = "Admin onayladı - Kullanıcı çalıştırabilir (executable)"
                else:
                    query_data.status = "approved"
                    workspace.show_results = False
                    workspace.description = "Admin onayladı - Kullanıcı çalıştıramaz (not executable)"
                
                await db.commit()
                
                return {
                    "success": True,
                    "status": query_data.status,
                    "message": f"Query approved successfully ({'executable' if show_results else 'not executable'})"
                }
            
            except Exception as e:
                await db.rollback()
                print(f"Approval failed: {e}")
                return {
                    "success": False,
                    "error": f"Approval failed: {str(e)}"
                }