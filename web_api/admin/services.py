"""
Admin Service Layer
Admin approval and management operations for risky queries
"""
from sqlalchemy import inspect, delete
from sqlalchemy.sql import select, text
from typing import Any
from app_database.models import QueryData, Workspace, User, Databases, MaskingRule
from app_database.app_database import AppDatabase
from database_provider import DatabaseProvider
from .schemas import AdminApprovals
from query_execution import config

import logging
from common.exceptions import BaseServiceException
from workspaces.exceptions import WorkspaceNotFoundError
from .exceptions import DatabaseAlreadyExistsError
from common.security import generate_secure_credentials

logger = logging.getLogger(__name__)

class BaseAdminService:
    """
    Base class for all admin services.
    Manages database connections for subclasses.
    """
    def __init__(self, app_db: AppDatabase, db_provider: DatabaseProvider):
        self.app_db = app_db
        self.db_provider = db_provider

class AdminService(BaseAdminService):
    """
    Main Admin Service.
    
    Combines sub-services (Approval, DB Addition) to provide a unified interface.
    """
    
    def __init__(self, app_db: AppDatabase, db_provider: DatabaseProvider):
        # Establish connections by calling the Base class's __init__
        super().__init__(app_db, db_provider)
        
        # Initialize sub-services
        self.approval_service = AdminApprovalService(app_db, db_provider)
        self.db_addition_service = AdminDBAdditionService(app_db, db_provider)
        
        # Other services to be added in the future can go here
        # self.report_service = AdminReportService(app_db, db_provider)

    # --- Approval Service Delegations ---
    # We define the methods used in the router as wrappers here
    # So we don't have to change the router code.

    async def get_workspaces_for_approval(self):
        return await self.approval_service.get_workspaces_for_approval()

    async def execute_for_preview(self, workspace_id: int, admin_user: User):
        return await self.approval_service.execute_for_preview(workspace_id, admin_user)

    async def reject_query_by_workspace_id(self, workspace_id: int):
        return await self.approval_service.reject_query_by_workspace_id(workspace_id)
            
    async def approve(self, workspace_id: int, show_results: bool):
        return await self.approval_service.approve(workspace_id, show_results)

    async def list_databases(self) -> list[Databases]:
        async with self.app_db.get_app_db() as db:
            result = await db.execute(select(Databases))
            return list(result.scalars().all())

    async def discover_schema(self, database_id: int, admin_user: User) -> dict[str, list[str]]:
        async with self.app_db.get_app_db() as db:
            db_entry = await db.get(Databases, database_id)
            if not db_entry:
                return {}
            servername = db_entry.servername
            database_name = db_entry.database_name
            
        db_info = await self.app_db.get_db_info()
        self.db_provider.set_db_info(db_info)
        
        try:
            async with self.db_provider.get_session(admin_user, servername, database_name) as session:
                def get_schema(connection):
                    inspector = inspect(connection)
                    schema = {}
                    
                    # Retrieve all schemas in the database
                    schemas = inspector.get_schema_names()
                    system_schemas = {
                        'sys', 'information_schema', 'guest', 'db_owner', 'db_accessadmin',
                        'db_securityadmin', 'db_ddladmin', 'db_backupoperator',
                        'db_datareader', 'db_datawriter', 'db_denydatareader', 'db_denydatawriter'
                    }
                    
                    for schema_name in schemas:
                        # Skip database role and system schemas
                        if schema_name.lower() in system_schemas or schema_name.lower().startswith('db_'):
                            continue
                        
                        try:
                            # Retrieve all tables in this schema
                            tables = inspector.get_table_names(schema=schema_name)
                            for table_name in tables:
                                # Format table names as "schema_name.table_name" for clear identification
                                full_table_name = f"{schema_name}.{table_name}"
                                schema[full_table_name] = [
                                    col["name"] for col in inspector.get_columns(table_name, schema=schema_name)
                                ]
                        except Exception as e:
                            logger.warning(f"Failed to inspect schema '{schema_name}' for database {database_id}: {e}")
                            continue
                            
                    return schema

                connection = await session.connection()
                schema = await connection.run_sync(get_schema)
                return schema
        except Exception as e:
            logger.error(f"Failed to discover schema for database {database_id}: {e}")
            return {}

    async def get_all_masking_rules(self, database_id: int) -> list[MaskingRule]:
        async with self.app_db.get_app_db() as db:
            result = await db.execute(
                select(MaskingRule).where(MaskingRule.database_id == database_id)
            )
            return list(result.scalars().all())

    async def save_masking_rules(self, database_id: int, rules_data: list) -> bool:
        async with self.app_db.get_app_db() as db:
            try:
                await db.execute(delete(MaskingRule).where(MaskingRule.database_id == database_id))
                for rule in rules_data:
                    new_rule = MaskingRule(
                        database_id=database_id,
                        table_name=rule.table_name,
                        column_name=rule.column_name,
                        masking_type=rule.masking_type,
                        is_active=rule.is_active
                    )
                    db.add(new_rule)
                await db.commit()
                return True
            except Exception as e:
                await db.rollback()
                logger.error(f"Failed to save masking rules for database {database_id}: {e}")
                return False

class AdminApprovalService(BaseAdminService):
    """
    Sub-service handling admin approval operations.
    """

    async def get_workspaces_for_approval(self):
        """
        Retrieves workspaces waiting for admin approval.
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
        Executes and previews the query for the admin.
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
                
                row_count: int = 0
                message: str | None = None
                result_data: list[dict[str, Any]] = []
                columns: list[str] = []
                
                if result.returns_rows:
                    rows = result.fetchmany(size=config.MAX_ROW_COUNT_LIMIT)
                    row_count = len(rows)
                    result_data = [dict(row._mapping) for row in rows]
                    columns = list(result_data[0].keys()) if result_data else []
                    if row_count >= config.MAX_ROW_COUNT_LIMIT:
                        message = f"Truncated to MAX_ROW_COUNT_LIMIT ({config.MAX_ROW_COUNT_LIMIT})"
                    else:
                        message = f"{row_count} rows returned"
                else:
                    row_count = result.rowcount if result.rowcount is not None else 0
                    message = f"{row_count} rows affected"
                    result_data = []
                    columns = []
            
            await self.app_db.update_log(
                log_id=log_id,
                successfull=True,
                row_count=row_count
            )

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
        Rejects the query.
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
                workspace.description = "Rejected by admin"
                
                await db.commit()
                return {"success": True}
                
            except Exception as e:
                await db.rollback()
                print(f"Error rejecting query: {e}")
                return {"success": False, "error": str(e)}
            
    async def approve(self, workspace_id: int, show_results: bool) -> dict[str, Any]:
        """
        Approves a query, enabling execution for the user.
        
        Args:
            workspace_id: The ID of the workspace containing the query.
            show_results: If True, the user can see execution results; otherwise, they cannot.
            
        Returns:
            dict[str, any]: A dictionary indicating success and the new query status.
        """
        async with self.app_db.get_app_db() as db:
            try:
                # 1. Fetch workspace by ID
                workspace_result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
                workspace: Workspace | None = workspace_result.scalars().first()
                if not workspace:
                    raise WorkspaceNotFoundError("Workspace not found")
                
                # 2. Fetch related QueryData
                query_result = await db.execute(select(QueryData).where(QueryData.id == workspace.query_id))
                query_data: QueryData | None = query_result.scalars().first()
                if not query_data:
                    raise WorkspaceNotFoundError("Query data not found for this workspace")
                
                # 3. Update status and description
                new_status: str = ""
                new_desc: str = ""
                if show_results:
                    new_status = "approved_with_results"
                    new_desc = "Approved by admin - User can execute"
                    workspace.show_results = True
                else:
                    new_status = "approved"
                    new_desc = "Approved by admin - User cannot execute"
                    workspace.show_results = False
                
                query_data.status = new_status
                workspace.description = new_desc
                
                await db.commit()
                
                logger.info(f"Query in workspace {workspace_id} approved by admin (Executable: {show_results})")
                return {
                    "success": True,
                    "status": new_status,
                    "message": f"Query approved successfully ({'executable' if show_results else 'not executable'})"
                }
            except BaseServiceException:
                raise
            except Exception as e:
                await db.rollback()
                logger.error(f"Approval failed for workspace {workspace_id}: {e}")
                raise BaseServiceException(f"Approval failed: {str(e)}", original_exception=e)

class AdminDBAdditionService(BaseAdminService):
    """
    Service for adding new databases to the platform configuration.
    """
    async def add_database(self, servername: str, database_name: str, tech_name: str) -> dict[str, Any]:
        """
        Adds a new database server and database configuration to the application databases.
        
        Args:
            servername: The host/instance name of the SQL server.
            database_name: The name of the database.
            tech_name: The database technology/type (e.g., mssql, postgresql, mysql).
            
        Returns:
            dict[str, any]: A dictionary containing execution status and a message or error.
        """
        async with self.app_db.get_app_db() as db:
            try:
                # Check if it already exists
                existing = await db.execute(select(Databases).where(
                    Databases.servername == servername, 
                    Databases.database_name == database_name
                ))
                existing_db: Databases | None = existing.scalars().first()
                if existing_db:
                    raise DatabaseAlreadyExistsError("Database already exists")

                db_username, db_password = generate_secure_credentials()

                database: Databases = Databases(
                    servername=servername, 
                    database_name=database_name, 
                    technology=tech_name,
                    db_username=db_username,
                    db_password=db_password
                )
                db.add(database)
                await db.commit()
                
                # Refresh db_provider db_info dynamically
                db_info = await self.app_db.get_db_info()
                self.db_provider.set_db_info(db_info)
                
                logger.info(f"Database '{database_name}' on server '{servername}' successfully added by admin with generated credentials")
                return {
                    "success": True, 
                    "message": "Database added successfully",
                    "db_username": db_username,
                    "db_password": db_password
                }
            except BaseServiceException:
                raise
            except Exception as e:
                await db.rollback()
                logger.error(f"Error adding database: {e}")
                raise BaseServiceException(f"Error adding database: {str(e)}", original_exception=e)
