"""
Admin Service Layer
Riskli query'lerin admin onayı ve yönetimi işlemleri
"""
from sqlalchemy.sql import select, text
from app_database.models import QueryData, Workspace, User, Databases
from app_database.app_database import AppDatabase
from database_provider import DatabaseProvider
from .schemas import *

class BaseAdminService:
    """
    Tüm admin servisleri için temel sınıf (Super Class).
    Veritabanı bağlantılarını yönetir.
    Java'daki Abstract Class mantığına benzer.
    Subclass'lar __init__ metodunu tekrar yazmak zorunda kalmaz.
    """
    def __init__(self, app_db: AppDatabase, db_provider: DatabaseProvider):
        self.app_db = app_db
        self.db_provider = db_provider

class AdminService(BaseAdminService):
    """
    Ana Admin Servisi
    
    Diğer alt servisleri (Approval, vb.) birleştirir ve dışarıya tek bir arayüz sunar.
    Facade Pattern benzeri bir yapı.
    """
    
    def __init__(self, app_db: AppDatabase, db_provider: DatabaseProvider):
        # Base class'ın __init__'ini çağırarak bağlantıları kur
        super().__init__(app_db, db_provider)
        
        # Alt servisleri initialize et
        self.approval_service = AdminApprovalService(app_db, db_provider)
        self.db_addition_service = AdminDBAdditionService(app_db, db_provider)
        
        # İleride eklenecek diğer servisler buraya gelebilir
        # self.report_service = AdminReportService(app_db, db_provider)

    # --- Approval Service Delegations ---
    # Router'da kullanılan metodları burada wrapper olarak tanımlıyoruz
    # Böylece router kodunu değiştirmek zorunda kalmıyoruz.

    async def get_workspaces_for_approval(self):
        return await self.approval_service.get_workspaces_for_approval()

    async def execute_for_preview(self, workspace_id: int, admin_user: User):
        return await self.approval_service.execute_for_preview(workspace_id, admin_user)

    async def reject_query_by_workspace_id(self, workspace_id: int):
        return await self.approval_service.reject_query_by_workspace_id(workspace_id)
            
    async def approve(self, workspace_id: int, show_results: bool):
        return await self.approval_service.approve(workspace_id, show_results)

class AdminApprovalService(BaseAdminService):
    """
    Admin onay işlemlerini yürüten alt servis.
    
    BaseAdminService'den miras aldığı için __init__ metodunu 
    tekrar yazmamıza gerek YOKTUR.
    self.app_db ve self.db_provider otomatik olarak gelir.
    """

    async def get_workspaces_for_approval(self):
        """
        Admin onayı bekleyen workspace'leri getirir
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
        Query'yi onaylar
        """
        try:
            async with self.app_db.get_app_db() as db:
                result = await db.execute(
                    text("SELECT query_id FROM Workspaces WHERE id = :workspace_id"),
                    {"workspace_id": workspace_id}
                )
                row = result.first()
                if not row:
                    return {"success": False, "error": "Workspace not found"}
                query_id = row[0]
            
            async with self.app_db.get_app_db() as db:
                result = await db.execute(
                    text("SELECT id FROM QueryData WHERE id = :query_id"),
                    {"query_id": query_id}
                )
                if not result.first():
                    return {"success": False, "error": "Query data not found"}
            
            if show_results:
                new_status = "approved_with_results"
                new_desc = "Admin onayladı - Kullanıcı çalıştırabilir (executable)"
                show_results_val = 1
            else:
                new_status = "approved"
                new_desc = "Admin onayladı - Kullanıcı çalıştıramaz (not executable)"
                show_results_val = 0
            
            async with self.app_db.get_app_db() as db:
                result1 = await db.execute(
                    text("UPDATE QueryData SET status = :status WHERE id = :id"),
                    {"status": new_status, "id": query_id}
                )
                
                result2 = await db.execute(
                    text("UPDATE Workspaces SET show_results = :show, description = :desc WHERE id = :id"),
                    {"show": show_results_val, "desc": new_desc, "id": workspace_id}
                )
                
                await db.commit()
            
            return {
                "success": True,
                "status": new_status,
                "message": f"Query approved successfully ({'executable' if show_results else 'not executable'})"
            }
        
        except Exception as e:
            print(f"Approval failed: {e}")
            return {
                "success": False,
                "error": f"Approval failed: {str(e)}"
            }

class AdminDBAdditionService(BaseAdminService):
    """
    Yeni veritabanı ekleme servisimiz. 
    BaseAdminService'den türediği için __init__ yazmadık.
    """
    async def add_database(self, servername: str, database_name: str, tech_name: str):
        """
        Yeni bir veritabanı ekler
        """
        async with self.app_db.get_app_db() as db:
            try:
                # Önce var mı diye kontrol et
                existing = await db.execute(select(Databases).where(
                    Databases.servername == servername, 
                    Databases.database_name == database_name
                ))
                if existing.scalars().first():
                    return {"success": False, "error": "Database already exists"}

                database = Databases(servername=servername, database_name=database_name, tech_name=tech_name)
                db.add(database)
                await db.commit()
                return {"success": True, "message": "Database added successfully"}
            except Exception as e:
                await db.rollback()
                print(f"Error adding database: {e}")
                return {"success": False, "error": str(e)}
