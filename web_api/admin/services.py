"""
Admin Service Layer
Admin approval and management operations for risky queries
"""
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, inspect, update
from sqlalchemy.sql import select, text

from app_database.app_database import AppDatabase
from app_database.models import (
    Databases,
    MaskingRule,
    QueryData,
    User,
    UserDatabaseAssociation,
    UserSession,
    Workspace,
)
from approval.service import decide
from common.audit import log_in, log_standalone
from common.audit_actions import AuditAction, AuditTarget
from common.audit_details import (
    DatabaseAccessAuditDetails,
    DatabaseConfigurationAuditDetails,
    MaskingRulesAuditDetails,
    QueryPreviewAuditDetails,
    UserLifecycleAuditDetails,
)
from common.constants import QUERY_STATUS_WAITING_FOR_APPROVAL
from common.exceptions import BaseServiceException
from common.roles import is_admin, parse
from common.security import generate_secure_credentials
from database_provider import DatabaseProvider
from query_execution import config

from .exceptions import (
    AdminUserNotFoundError,
    CannotDisableSelfError,
    DatabaseAlreadyExistsError,
)
from .schemas import AdminApprovals

logger = logging.getLogger(__name__)


def _db_now() -> datetime:
    """Return naive UTC for the cross-database AppDateTime columns."""
    return datetime.now(UTC).replace(tzinfo=None)

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
        self.auth_service = AdminUserAuthService(app_db, db_provider)
        
        # Other services to be added in the future can go here
        # self.report_service = AdminReportService(app_db, db_provider)

    # --- Approval Service Delegations ---
    # We define the methods used in the router as wrappers here
    # So we don't have to change the router code.

    async def get_workspaces_for_approval(self, admin_user: User):
        return await self.approval_service.get_workspaces_for_approval(admin_user)

    async def execute_for_preview(
        self, workspace_id: int, admin_user: User, client_ip: str | None = None
    ):
        return await self.approval_service.execute_for_preview(
            workspace_id, admin_user, client_ip
        )

    async def reject_query_by_workspace_id(
        self,
        workspace_id: int,
        reason: str,
        admin_user: User,
        client_ip: str | None = None,
    ):
        return await self.approval_service.reject_query_by_workspace_id(
            workspace_id, reason, admin_user, client_ip
        )
            
    async def approve(
        self,
        workspace_id: int,
        show_results: bool,
        admin_user: User,
        client_ip: str | None = None,
    ):
        return await self.approval_service.approve(
            workspace_id, show_results, admin_user, client_ip
        )
 
    async def associate_user_to_database(
        self,
        user_id: int,
        database_id: int,
        role: str,
        admin_user: User,
        client_ip: str | None = None,
    ) -> dict[str, Any]:
        return await self.auth_service.associate_user_to_database(
            user_id, database_id, role, admin_user, client_ip
        )

    async def disable_user(
        self,
        user_id: int,
        admin_user: User,
        client_ip: str | None = None,
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        return await self.auth_service.disable_user(
            user_id, admin_user, client_ip, trace_id
        )

    async def list_users(self) -> list[User]:
        return await self.auth_service.list_users()

    async def enable_user(
        self,
        user_id: int,
        admin_user: User,
        client_ip: str | None = None,
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        return await self.auth_service.enable_user(
            user_id, admin_user, client_ip, trace_id
        )

    async def list_databases(self, admin_user: User) -> list[Databases]:
        async with self.app_db.get_app_db() as db:
            stmt = select(Databases).join(
                UserDatabaseAssociation,
                UserDatabaseAssociation.database_id == Databases.id
            ).where(
                UserDatabaseAssociation.user_id == admin_user.id
            )
            result = await db.execute(stmt)
            all_dbs = result.scalars().all()
            
            filtered = []
            for db_entry in all_dbs:
                stmt_assoc = select(UserDatabaseAssociation).where(
                    UserDatabaseAssociation.user_id == admin_user.id,
                    UserDatabaseAssociation.database_id == db_entry.id
                )
                res_assoc = await db.execute(stmt_assoc)
                assoc = res_assoc.scalars().first()
                if assoc and is_admin(assoc.role):
                    filtered.append(db_entry)
            return filtered

    async def discover_schema(self, database_id: int, admin_user: User) -> dict[str, list[str]]:
        async with self.app_db.get_app_db() as db:
            assoc_res = await db.execute(
                select(UserDatabaseAssociation).where(
                    UserDatabaseAssociation.user_id == admin_user.id,
                    UserDatabaseAssociation.database_id == database_id
                )
            )
            assoc = assoc_res.scalars().first()
            if not assoc or not is_admin(assoc.role):
                return {}

            db_entry = await db.get(Databases, database_id)
            if not db_entry:
                return {}

        db_info = await self.app_db.get_db_info()
        self.db_provider.set_db_info(db_info)
        
        try:
            async with self.db_provider.get_session(admin_user, str(db_entry.uuid)) as session:
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

    async def get_all_masking_rules(self, database_id: int, admin_user: User) -> list[MaskingRule]:
        async with self.app_db.get_app_db() as db:
            assoc_res = await db.execute(
                select(UserDatabaseAssociation).where(
                    UserDatabaseAssociation.user_id == admin_user.id,
                    UserDatabaseAssociation.database_id == database_id
                )
            )
            assoc = assoc_res.scalars().first()
            if not assoc or not is_admin(assoc.role):
                raise BaseServiceException("You do not have admin permissions for this database.")

            result = await db.execute(
                select(MaskingRule).where(MaskingRule.database_id == database_id)
            )
            return list(result.scalars().all())

    async def save_masking_rules(
        self,
        database_id: int,
        rules_data: list,
        admin_user: User,
        client_ip: str | None = None,
    ) -> bool:
        action = AuditAction.UPDATE_MASKING_RULES
        async with self.app_db.get_app_db() as db:
            try:
                async with db.begin():
                    assoc_res = await db.execute(
                        select(UserDatabaseAssociation).where(
                            UserDatabaseAssociation.user_id == admin_user.id,
                            UserDatabaseAssociation.database_id == database_id
                        )
                    )
                    assoc = assoc_res.scalars().first()
                    if not assoc or not is_admin(assoc.role):
                        raise BaseServiceException(
                            "You do not have admin permissions for this database."
                        )

                    existing_result = await db.execute(
                        select(MaskingRule).where(MaskingRule.database_id == database_id)
                    )
                    details = MaskingRulesAuditDetails.from_rule_sets(
                        existing_result.scalars().all(), rules_data
                    )

                    await db.execute(
                        delete(MaskingRule).where(MaskingRule.database_id == database_id)
                    )
                    for rule in rules_data:
                        db.add(
                            MaskingRule(
                                database_id=database_id,
                                table_name=rule.table_name,
                                column_name=rule.column_name,
                                masking_type=rule.masking_type,
                                is_active=rule.is_active,
                            )
                        )

                    if details.has_changes:
                        await log_in(
                            db,
                            actor=admin_user,
                            action=action,
                            target_type=AuditTarget.DATABASE,
                            target_id=database_id,
                            details=details,
                            client_ip=client_ip,
                        )
                return True
            except Exception as e:
                logger.error(f"Failed to save masking rules for database {database_id}: {e}")
                return False

class AdminApprovalService(BaseAdminService):
    """
    Sub-service handling admin approval operations.
    """

    async def get_workspaces_for_approval(self, admin_user: User):
        """
        Retrieves workspaces waiting for admin approval for the databases the admin is associated with as ADMIN.
        """
        result_list = []
        try:
            async with self.app_db.get_app_db() as db:
                # We need to query QueryData where status is waiting_for_approval,
                # then filter to databases where this user is ADMIN
                stmt = select(QueryData).where(
                    QueryData.status == QUERY_STATUS_WAITING_FOR_APPROVAL
                )
                results = await db.execute(stmt)
                queries = results.scalars().all()
                if queries:
                    for query in queries:
                        # Check admin permissions on the query database
                        db_res = await db.execute(
                            select(Databases).where(Databases.servername == query.servername, Databases.database_name == query.database_name)
                        )
                        db_entry = db_res.scalars().first()
                        if not db_entry:
                            continue
                            
                        assoc_res = await db.execute(
                            select(UserDatabaseAssociation).where(
                                UserDatabaseAssociation.user_id == admin_user.id,
                                UserDatabaseAssociation.database_id == db_entry.id
                            )
                        )
                        assoc = assoc_res.scalars().first()
                        if not assoc or not is_admin(assoc.role):
                            continue

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
            print(f"Error: {e!s}")
            return []
        
    async def execute_for_preview(
        self, workspace_id: int, admin_user: User, client_ip: str | None = None
    ):
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
            
            # Resolve db_uuid from Databases table
            db_res = await db.execute(
                select(Databases).where(Databases.servername == servername, Databases.database_name == database_name)
            )
            db_entry = db_res.scalars().first()
            if not db_entry:
                return {"success": False, "error": "Database not registered in Databases table"}
            db_uuid = str(db_entry.uuid)
            
            # Check admin permissions on the target database
            assoc_res = await db.execute(
                select(UserDatabaseAssociation).where(
                    UserDatabaseAssociation.user_id == admin_user.id,
                    UserDatabaseAssociation.database_id == db_entry.id
                )
            )
            assoc = assoc_res.scalars().first()
            if not assoc or not is_admin(assoc.role):
                return {"success": False, "error": "You do not have admin permissions for this database."}
        
        try:
            log_id = await self.app_db.create_log(
                user=admin_user, 
                query=query_text, 
                machine_name=servername
            )
            
            async with self.db_provider.get_session(user, db_uuid) as session:
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
            await log_standalone(
                self.app_db,
                action=AuditAction.PREVIEW_QUERY,
                actor=admin_user,
                target_type=AuditTarget.QUERY,
                target_id=query_data.id,
                details=QueryPreviewAuditDetails(
                    query_id=query_data.id, database_id=db_entry.id, row_count=row_count,
                    truncated=row_count >= config.MAX_ROW_COUNT_LIMIT,
                ),
                client_ip=client_ip,
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

    async def reject_query_by_workspace_id(
        self,
        workspace_id: int,
        reason: str,
        admin_user: User,
        client_ip: str | None = None,
    ) -> dict[str, Any]:
        """Reject through the shared, transport-independent approval service."""
        outcome = await decide(
            self.app_db,
            workspace_id=workspace_id,
            decision="reject",
            actor=admin_user,
            reason=reason,
            client_ip=client_ip,
        )
        return {"success": True, "status": outcome.new_status}
            
    async def approve(
        self,
        workspace_id: int,
        show_results: bool,
        admin_user: User,
        client_ip: str | None = None,
    ) -> dict[str, Any]:
        """Approve through the shared, transport-independent approval service."""
        outcome = await decide(
            self.app_db,
            workspace_id=workspace_id,
            decision=("approve_with_results" if show_results else "approve_no_results"),
            actor=admin_user,
            client_ip=client_ip,
        )
        return {
            "success": True,
            "status": outcome.new_status,
            "message": (
                "Query approved successfully "
                f"({'executable' if show_results else 'not executable'})"
            ),
        }

class AdminDBAdditionService(BaseAdminService):
    """
    Service for adding new databases to the platform configuration.
    """
    async def add_database(
        self,
        servername: str,
        database_name: str,
        tech_name: str,
        admin_user: User,
        client_ip: str | None = None,
    ) -> dict[str, Any]:
        """
        Adds a new database server and database configuration to the application databases.
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
                db_uuid = str(uuid.uuid4())

                database: Databases = Databases(
                    servername=servername, 
                    database_name=database_name, 
                    technology=tech_name,
                    db_username=db_username,
                    db_password=db_password,
                    uuid=db_uuid
                )
                db.add(database)
                await db.flush()
                db.add(UserDatabaseAssociation(user_id=admin_user.id, database_id=database.id,
                    role="ADMIN", is_admin=True))
                await log_in(db, actor=admin_user, action=AuditAction.ADD_DATABASE,
                    target_type=AuditTarget.DATABASE, target_id=database.id,
                    details=DatabaseConfigurationAuditDetails(operation="add", servername=servername,
                        database_name=database_name, technology=tech_name),
                    client_ip=client_ip)
                await db.commit()
                
                # Refresh db_provider db_info dynamically
                db_info = await self.app_db.get_db_info()
                self.db_provider.set_db_info(db_info)
                
                logger.info(f"Database '{database_name}' on server '{servername}' (UUID: {db_uuid}) successfully added by admin {admin_user.id} with generated credentials")
                return {
                    "success": True, 
                    "message": "Database added successfully",
                    "db_uuid": db_uuid,
                    "db_username": db_username,
                    "db_password": db_password
                }
            except BaseServiceException:
                raise
            except Exception as e:
                logger.error(f"Error adding database: {e}")
                raise BaseServiceException(f"Error adding database: {e!s}", original_exception=e)


class AdminUserAuthService(BaseAdminService):
    """
    Sub-service for admin to manage user database associations and roles.
    """

    async def list_users(self) -> list[User]:
        async with self.app_db.get_app_db() as db:
            result = await db.execute(select(User).order_by(User.username.asc()))
            return list(result.scalars().all())

    async def enable_user(
        self,
        user_id: int,
        admin_user: User,
        client_ip: str | None = None,
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        """Activate a pending/disabled account and record the transition."""
        async with self.app_db.get_app_db() as db, db.begin():
            target = await db.get(User, user_id)
            if target is None:
                raise AdminUserNotFoundError("Kullanıcı bulunamadı.")

            if target.is_active:
                return {"success": True, "message": "User is already active"}

            target.is_active = True
            target.disabled_at = None
            target.disabled_by = None
            await log_in(
                db,
                actor=admin_user,
                action=AuditAction.USER_ENABLED,
                target_type=AuditTarget.USER,
                target_id=user_id,
                details=UserLifecycleAuditDetails(event="enabled", source="admin"),
                client_ip=client_ip,
                trace_id=trace_id,
            )

        return {"success": True, "message": "User enabled successfully"}

    async def disable_user(
        self,
        user_id: int,
        admin_user: User,
        client_ip: str | None = None,
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        """Disable a user and revoke all of the user's active sessions."""
        if user_id == admin_user.id:
            raise CannotDisableSelfError("Kendi hesabınızı devre dışı bırakamazsınız.")

        async with self.app_db.get_app_db() as db, db.begin():
            target = await db.get(User, user_id)
            if target is None:
                raise AdminUserNotFoundError("Kullanıcı bulunamadı.")

            if target.is_active:
                target.is_active = False
                target.disabled_at = _db_now()
                target.disabled_by = admin_user.username
            elif target.disabled_at is None:
                # Preserve the original disable actor/time when present,
                # while making legacy/incomplete rows safe to finish.
                target.disabled_at = _db_now()
                target.disabled_by = admin_user.username

            await db.execute(
                update(UserSession)
                .where(
                    UserSession.user_id == user_id,
                    UserSession.revoked_at.is_(None),
                )
                .values(
                    revoked_at=_db_now(),
                    revoked_reason="user disabled",
                )
            )

            await log_in(
                db,
                actor=admin_user,
                action=AuditAction.USER_DISABLED,
                target_type=AuditTarget.USER,
                target_id=user_id,
                details=UserLifecycleAuditDetails(event="disabled", source="admin"),
                client_ip=client_ip,
                trace_id=trace_id,
            )

        return {"success": True, "message": "User disabled successfully"}

    async def associate_user_to_database(
        self,
        user_id: int,
        database_id: int,
        role: str,
        admin_user: User,
        client_ip: str | None = None,
    ) -> dict[str, Any]:
        role_upper = role.upper()
        # Clean roles list, allow comma-separated combination of READER, WRITER, ADMIN
        roles_list = parse(role)
        if not roles_list or any(r not in ["READER", "WRITER", "ADMIN"] for r in roles_list):
            raise BaseServiceException("Invalid role. Role must be READER, WRITER, or ADMIN.")
            
        async with self.app_db.get_app_db() as db:
            # Check admin permission
            assoc_res_admin = await db.execute(
                select(UserDatabaseAssociation).where(
                    UserDatabaseAssociation.user_id == admin_user.id,
                    UserDatabaseAssociation.database_id == database_id
                )
            )
            assoc_admin = assoc_res_admin.scalars().first()
            if not assoc_admin or not is_admin(assoc_admin.role):
                raise BaseServiceException("You do not have admin permissions for this database.")

            # Check user exists
            user_res = await db.execute(select(User).where(User.id == user_id))
            user = user_res.scalars().first()
            if not user:
                raise BaseServiceException("User not found.")
                
            # Check database exists
            db_res = await db.execute(select(Databases).where(Databases.id == database_id))
            db_entry = db_res.scalars().first()
            if not db_entry:
                raise BaseServiceException("Database not found.")
                
            # Check existing association
            assoc_res = await db.execute(
                select(UserDatabaseAssociation).where(
                    UserDatabaseAssociation.user_id == user_id,
                    UserDatabaseAssociation.database_id == database_id
                )
            )
            assoc = assoc_res.scalars().first()
            
            is_admin_val = (role_upper == "ADMIN")
            
            previous_role = assoc.role if assoc else None
            if assoc:
                assoc.role = role_upper
                assoc.is_admin = is_admin_val
            else:
                assoc = UserDatabaseAssociation(
                    user_id=user_id,
                    database_id=database_id,
                    role=role_upper,
                    is_admin=is_admin_val
                )
                db.add(assoc)
                
            if previous_role != role_upper:
                action = (AuditAction.CHANGE_DATABASE_ROLE if assoc and previous_role
                          else AuditAction.GRANT_DATABASE_ACCESS)
                await log_in(db, actor=admin_user, action=action, target_type=AuditTarget.USER,
                    target_id=user_id, details=DatabaseAccessAuditDetails(
                        operation="change_role" if previous_role else "grant", database_id=database_id,
                        previous_role=previous_role, new_role=role_upper), client_ip=client_ip)
            await db.commit()
            
        return {"success": True, "message": f"Successfully associated user {user_id} with database {database_id} as {role_upper}."}
