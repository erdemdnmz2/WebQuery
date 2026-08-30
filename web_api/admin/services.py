"""
Admin Service Layer
Admin approval and management operations for risky queries
"""
import logging
from typing import Any

import sqlglot.errors
from sqlalchemy import String, and_, cast, delete, inspect, or_
from sqlalchemy.sql import select

from app_database.app_database import AppDatabase
from app_database.models import (
    AuditLog,
    Databases,
    MaskingRule,
    QueryData,
    User,
    UserDatabaseAssociation,
    Workspace,
)
from approval.service import decide
from common.audit import log_in, log_standalone
from common.audit_actions import AuditAction, AuditTarget
from common.audit_details import (
    DatabaseAccessAuditDetails,
    MaskingRulesAuditDetails,
    QueryPreviewAuditDetails,
)
from common.constants import QUERY_STATUS_WAITING_FOR_APPROVAL
from common.errors import redact_passwords, scrub
from common.exceptions import BaseServiceException
from common.roles import (
    ADMIN,
    exceeds_mode,
    format_roles,
    is_admin,
    mode_from_credentials,
    parse,
)
from database_provider import DatabaseProvider
from query_execution import config
from query_execution.query_analyzer import QueryAnalyzer, hard_block_reason_for
from query_execution.runner import run_statement

from .exceptions import (
    DatabaseAccessNotFoundError,
    DatabaseAdminOwnerRequiredError,
    DatabaseAdminRequiredError,
    DatabaseNotFoundError,
    RoleNotSupportedByDatabaseError,
)
from .schemas import AdminApprovals

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
    
    Combines database-scoped approval and access services.
    """
    
    def __init__(self, app_db: AppDatabase, db_provider: DatabaseProvider):
        # Establish connections by calling the Base class's __init__
        super().__init__(app_db, db_provider)
        
        # Initialize sub-services
        self.approval_service = AdminApprovalService(app_db, db_provider)
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
    # `list_database_users` and `revoke_user_from_database` are defined on this
    # class directly, below; they read the same association table this service
    # already owns and need no sub-service indirection.

    async def list_database_users(
        self, database_id: int, admin_user: User
    ) -> dict[str, Any]:
        """Users holding access to one database, plus who else could be granted it.

        A database ADMIN had no way to discover a `user_id`, so
        `POST /api/admin/associate_user` — the only path to granting query
        access — was unusable from the interface: an activated user could reach
        no database at all. `/api/owner/users` is OWNER-only and stays that way.

        Disclosure is deliberately narrow. The candidate list is username and
        email of *active* users only, which is what naming a colleague to grant
        requires; it carries no lifecycle, owner or role information.
        """
        async with self.app_db.get_app_db() as db:
            assoc = (
                await db.execute(
                    select(UserDatabaseAssociation).where(
                        UserDatabaseAssociation.user_id == admin_user.id,
                        UserDatabaseAssociation.database_id == database_id,
                    )
                )
            ).scalars().first()
            if not assoc or not is_admin(assoc.role):
                raise DatabaseAdminRequiredError(
                    "You do not have admin permissions for this database."
                )

            database = await db.get(Databases, database_id)
            if database is None:
                raise DatabaseNotFoundError("Database not found.")

            # One join instead of a query per member.
            rows = (
                await db.execute(
                    select(User, UserDatabaseAssociation)
                    .join(
                        UserDatabaseAssociation,
                        UserDatabaseAssociation.user_id == User.id,
                    )
                    .where(UserDatabaseAssociation.database_id == database_id)
                    .order_by(User.username.asc())
                )
            ).all()
            members = [
                {
                    "user_id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "role": association.role,
                    "is_admin": is_admin(association.role),
                    "is_active": bool(user.is_active),
                }
                for user, association in rows
            ]

            member_ids = {member["user_id"] for member in members}
            candidates = [
                {"user_id": user.id, "username": user.username, "email": user.email}
                for user in (
                    await db.execute(
                        select(User)
                        .where(User.is_active.is_(True))
                        .order_by(User.username.asc())
                    )
                ).scalars().all()
                if user.id not in member_ids
            ]

        return {
            "database_id": database_id,
            "connection_mode": mode_from_credentials(
                has_ro=bool(database.username_ro and database.password_ro),
                has_rw=bool(database.username_rw and database.password_rw),
                has_ddl=bool(database.username_ddl and database.password_ddl),
            ),
            "members": members,
            "candidates": candidates,
        }

    async def revoke_user_from_database(
        self,
        database_id: int,
        user_id: int,
        admin_user: User,
        client_ip: str | None = None,
    ) -> dict[str, Any]:
        """Remove a user's data-access roles on one database.

        Until this existed, `AuditAction.REVOKE_DATABASE_ACCESS` had no call
        site because there was no way to take access away:
        `associate_user_to_database` can only replace roles, and an empty role
        is rejected. The only way to cut off a departing employee was to disable
        their account entirely, which also removed their access everywhere else.

        The DB ADMIN role is left untouched — it is a governance root that only
        the platform OWNER manages (`/api/owner/databases/{id}/admins/{uid}`).
        Revoking data roles from a user who is also ADMIN leaves them ADMIN.
        """
        async with self.app_db.get_app_db() as db:
            async with db.begin():
                admin_assoc = (
                    await db.execute(
                        select(UserDatabaseAssociation).where(
                            UserDatabaseAssociation.user_id == admin_user.id,
                            UserDatabaseAssociation.database_id == database_id,
                        )
                    )
                ).scalars().first()
                if not admin_assoc or not is_admin(admin_assoc.role):
                    raise DatabaseAdminRequiredError(
                        "You do not have admin permissions for this database."
                    )

                target = (
                    await db.execute(
                        select(UserDatabaseAssociation)
                        .where(
                            UserDatabaseAssociation.user_id == user_id,
                            UserDatabaseAssociation.database_id == database_id,
                        )
                        .with_for_update()
                    )
                ).scalars().first()
                if target is None:
                    raise DatabaseAccessNotFoundError(
                        "Bu kullanıcının bu veritabanında erişimi yok."
                    )

                previous_role = target.role
                remaining = parse(previous_role) & {ADMIN}
                if not (parse(previous_role) - {ADMIN}):
                    raise DatabaseAdminOwnerRequiredError(
                        "Bu kullanıcının kaldırılacak bir veri erişimi yok. "
                        "DB ADMIN yetkisini platform OWNER yönetir."
                    )

                new_role = format_roles(remaining) if remaining else None
                if new_role is None:
                    await db.delete(target)
                else:
                    target.role = new_role
                    target.is_admin = True

                # Same transaction as the deletion: if the write fails, the
                # audit row goes with it rather than claiming a revoke that
                # never happened.
                await log_in(
                    db,
                    actor=admin_user,
                    action=AuditAction.REVOKE_DATABASE_ACCESS,
                    target_type=AuditTarget.USER,
                    target_id=user_id,
                    details=DatabaseAccessAuditDetails(
                        operation="revoke",
                        database_id=database_id,
                        previous_role=previous_role,
                        new_role=new_role,
                    ),
                    client_ip=client_ip,
                )

        return {
            "success": True,
            "message": "Veritabanı erişimi kaldırıldı.",
            "remaining_role": new_role,
        }

    async def list_databases(self, admin_user: User) -> list[Databases]:
        """Databases on which the caller holds ADMIN.

        The join already carries the association row, so the ADMIN test reads
        it directly. This used to re-query the same association once per
        database — a second round trip per row to re-fetch data already in hand.
        The role is a comma-separated string, so the filter stays in Python.
        """
        async with self.app_db.get_app_db() as db:
            rows = (
                await db.execute(
                    select(Databases, UserDatabaseAssociation.role)
                    .join(
                        UserDatabaseAssociation,
                        UserDatabaseAssociation.database_id == Databases.id,
                    )
                    .where(
                        UserDatabaseAssociation.user_id == admin_user.id,
                        Databases.is_active.is_(True),
                    )
                )
            ).all()
            return [database for database, role in rows if is_admin(role)]

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
                # Answering {} made "you have no permission" and "this database
                # has no tables" the same response, so the client could not tell
                # a misconfiguration from an authorization failure.
                raise DatabaseAdminRequiredError(
                    "You do not have admin permissions for this database."
                )

            db_entry = await db.get(Databases, database_id)
            if not db_entry:
                raise DatabaseNotFoundError("Database not found.")

        # The catalogue is refreshed when a registration changes (OWNER
        # add/update/remove), not on every schema scan. Reloading here decrypted
        # every registered database's credentials to inspect one of them, and
        # rewrote shared provider state underneath any concurrent request.

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
                raise DatabaseAdminRequiredError("You do not have admin permissions for this database.")

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
            except BaseServiceException:
                # An authorization failure is not a save failure. Catching it
                # here turned "you are not an admin of this database" into the
                # same generic 400 as a driver error, so neither the user nor
                # the operator could tell what to fix.
                raise
            except ValueError as exc:
                # MaskingRulesAuditDetails rejects the same table+column twice.
                raise BaseServiceException(str(exc), original_exception=exc) from exc
            except Exception as e:
                logger.error(f"Failed to save masking rules for database {database_id}: {e}")
                return False

    async def admin_database_ids(self, admin_user: User) -> list[int]:
        """Return the database ids on which this user actually holds ADMIN.

        `admin_required` only asks whether the caller is ADMIN on *at least one*
        database; every scoped operation has to narrow from there itself.
        """
        async with self.app_db.get_app_db() as db:
            result = await db.execute(
                select(UserDatabaseAssociation).where(
                    UserDatabaseAssociation.user_id == admin_user.id
                )
            )
            return [
                assoc.database_id
                for assoc in result.scalars().all()
                if is_admin(assoc.role)
            ]

    async def get_audit_log(
        self,
        admin_user: User,
        *,
        action: AuditAction | None = None,
        target_type: AuditTarget | None = None,
        target_id: str | None = None,
        limit: int = 200,
    ) -> list[AuditLog]:
        """Return audit records the caller is entitled to see, newest first.

        This endpoint used to return the whole `AuditLog` table to anyone who was
        ADMIN on any one database: other databases' access changes, OWNER
        operations, and every user's login history. Every other method in this
        module re-checks ADMIN on the specific `database_id`; this was the
        exception.

        Scoping now follows the record's subject:

        * platform OWNER sees everything, including user, session and login
          records, which are platform-level and belong to no single database;
        * a database ADMIN sees records about the databases they administer —
          `database` targets directly, plus the `workspace`/`query` records for
          queries that ran against those databases, so their own approval
          history stays visible.
        """
        is_platform_owner = bool(getattr(admin_user, "is_platform_owner", False))

        async with self.app_db.get_app_db() as db:
            statement = select(AuditLog).order_by(AuditLog.id.desc()).limit(limit)
            if action is not None:
                statement = statement.where(AuditLog.action == action)
            if target_type is not None:
                statement = statement.where(AuditLog.target_type == target_type)
            if target_id is not None:
                statement = statement.where(AuditLog.target_id == str(target_id))

            if not is_platform_owner:
                database_ids = [
                    assoc.database_id
                    for assoc in (
                        await db.execute(
                            select(UserDatabaseAssociation).where(
                                UserDatabaseAssociation.user_id == admin_user.id
                            )
                        )
                    )
                    .scalars()
                    .all()
                    if is_admin(assoc.role)
                ]
                if not database_ids:
                    return []

                # `target_id` is stored as text, so each scoped id set is
                # compared as text too.
                database_targets = [str(database_id) for database_id in database_ids]

                # Queries reach a database through (servername, database_name);
                # there is no FK yet (see docs/inbox/DATABASE-EXTERNAL-IDENTIFIER-UUID.md).
                scoped_query_ids = (
                    select(QueryData.id)
                    .join(
                        Databases,
                        (Databases.servername == QueryData.servername)
                        & (Databases.database_name == QueryData.database_name),
                    )
                    .where(Databases.id.in_(database_ids))
                    .subquery()
                )
                scoped_workspace_ids = (
                    select(Workspace.id)
                    .where(Workspace.query_id.in_(select(scoped_query_ids.c.id)))
                    .subquery()
                )

                statement = statement.where(
                    or_(
                        and_(
                            AuditLog.target_type == AuditTarget.DATABASE,
                            AuditLog.target_id.in_(database_targets),
                        ),
                        and_(
                            AuditLog.target_type == AuditTarget.QUERY,
                            AuditLog.target_id.in_(
                                select(cast(scoped_query_ids.c.id, String))
                            ),
                        ),
                        and_(
                            AuditLog.target_type == AuditTarget.WORKSPACE,
                            AuditLog.target_id.in_(
                                select(cast(scoped_workspace_ids.c.id, String))
                            ),
                        ),
                    )
                )

            return list((await db.execute(statement)).scalars().all())


class AdminApprovalService(BaseAdminService):
    """
    Sub-service handling admin approval operations.
    """

    async def get_workspaces_for_approval(self, admin_user: User):
        """
        Retrieves workspaces waiting for admin approval for the databases the admin is associated with as ADMIN.
        """
        try:
            async with self.app_db.get_app_db() as db:
                # One join across the four tables the queue needs. This used to
                # issue four separate SELECTs per pending query (Databases,
                # association, Workspace, User), so a queue of 50 cost over 200
                # round trips.
                rows = (
                    await db.execute(
                        select(QueryData, Workspace, User, UserDatabaseAssociation.role)
                        .join(Workspace, Workspace.query_id == QueryData.id)
                        .join(User, User.id == QueryData.user_id)
                        .join(
                            Databases,
                            (Databases.servername == QueryData.servername)
                            & (Databases.database_name == QueryData.database_name),
                        )
                        .join(
                            UserDatabaseAssociation,
                            (UserDatabaseAssociation.database_id == Databases.id)
                            & (UserDatabaseAssociation.user_id == admin_user.id),
                        )
                        .where(QueryData.status == QUERY_STATUS_WAITING_FOR_APPROVAL)
                        .order_by(QueryData.id.desc())
                    )
                ).all()

            # The role is a comma-separated string, so ADMIN is still resolved
            # in Python rather than by the database.
            return [
                AdminApprovals(
                    user_id=query.user_id,
                    workspace_id=workspace.id,
                    username=user.username,
                    query=query.query,
                    database=query.database_name,
                    status=query.status,
                    risk_type=query.risk_type,
                    servername=query.servername,
                )
                for query, workspace, user, role in rows
                if is_admin(role)
            ]
        except Exception as exc:
            logger.error("Onay bekleyen çalışma alanları alınamadı: %s", type(exc).__name__)
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
            
            analyzer = QueryAnalyzer()
            try:
                plan = analyzer.plan(query_text, technology=db_entry.technology)
            except sqlglot.errors.ParseError:
                reason = "Sorgu ayrıştırılamadı ve güvenlik gereği engellendi."
                await self.app_db.update_log(log_id=log_id, successfull=False, error=reason)
                return {"success": False, "error": reason}

            # Previewing runs the statement on the target database, so the
            # checks nobody may skip apply here as well.
            blocked = hard_block_reason_for(analyzer, plan)
            if blocked:
                await self.app_db.update_log(log_id=log_id, successfull=False, error=blocked)
                return {"success": False, "error": blocked}

            async with self.db_provider.get_session(user, db_uuid, tier=plan.tier) as session:
                outcome = await run_statement(session, plan, config.MAX_ROW_COUNT_LIMIT)

            row_count: int = outcome.row_count
            message: str | None = outcome.message
            result_data: list[dict[str, Any]] = outcome.rows
            columns: list[str] = list(result_data[0].keys()) if result_data else []

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
                details=QueryPreviewAuditDetails(
                    query_id=query_data.id, database_id=db_entry.id, row_count=row_count,
                    truncated=outcome.truncated,
                ),
                target_id=query_data.id,
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
        except Exception as exc:
            # The other three execution paths redact passwords before logging
            # and scrub connection details before answering. The preview used
            # raw `str(exc)` for both, so a driver error naming the target host
            # or credentials reached the admin screen verbatim; being an admin
            # surface does not make that an intended disclosure.
            error_msg = str(exc)
            safe_log_error = redact_passwords(error_msg)
            if log_id:
                await self.app_db.update_log(
                    log_id=log_id,
                    successfull=False,
                    error=safe_log_error,
                )

            logger.error("Sorgu önizlemesi başarısız oldu: %s", type(exc).__name__)
            return {
                "response_type": "error",
                "data": [],
                "columns": [],
                "row_count": 0,
                "message": None,
                "error": scrub(error_msg),
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

class AdminUserAuthService(BaseAdminService):
    """
    Sub-service for admin to manage user database associations and roles.
    """

    async def associate_user_to_database(
        self,
        user_id: int,
        database_id: int,
        role: str,
        admin_user: User,
        client_ip: str | None = None,
    ) -> dict[str, Any]:
        # DB ADMIN is a governance root managed only by OWNER. This endpoint
        # may replace data roles, but it must neither grant nor accidentally
        # erase an existing ADMIN role.
        roles_list = parse(role)
        if ADMIN in roles_list:
            raise DatabaseAdminOwnerRequiredError(
                "DB ADMIN atamalarını yalnızca platform OWNER yönetebilir."
            )
        if not roles_list or any(r not in ["READER", "WRITER", "DDL"] for r in roles_list):
            raise BaseServiceException("Invalid role. Role must be READER, WRITER, or DDL.")
        requested_role = format_roles(roles_list)
            
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
                raise DatabaseAdminRequiredError("You do not have admin permissions for this database.")

            # Check user exists
            user_res = await db.execute(select(User).where(User.id == user_id))
            user = user_res.scalars().first()
            if not user:
                raise BaseServiceException("User not found.")
                
            # Check database exists
            db_res = await db.execute(select(Databases).where(Databases.id == database_id))
            db_entry = db_res.scalars().first()
            if not db_entry:
                raise DatabaseNotFoundError("Database not found.")

            # A grant may not exceed the tiers the DBA actually provisioned.
            # Without this the grant succeeds and every query at that tier
            # fails closed later, with nothing pointing back at the grant.
            connection_mode = mode_from_credentials(
                has_ro=bool(db_entry.username_ro and db_entry.password_ro),
                has_rw=bool(db_entry.username_rw and db_entry.password_rw),
                has_ddl=bool(db_entry.username_ddl and db_entry.password_ddl),
            )
            unsupported_tier = exceeds_mode(connection_mode, requested_role)
            if unsupported_tier:
                raise RoleNotSupportedByDatabaseError(
                    f"Bu veritabanı '{connection_mode}' bağlantı moduyla kayıtlı; "
                    f"'{unsupported_tier.upper()}' kademesi tanımlı değil. "
                    "Önce veritabanı kaydına bu kademenin kimlik bilgilerini ekleyin."
                )
                
            # Check existing association
            assoc_res = await db.execute(
                select(UserDatabaseAssociation).where(
                    UserDatabaseAssociation.user_id == user_id,
                    UserDatabaseAssociation.database_id == database_id
                )
            )
            assoc = assoc_res.scalars().first()
            
            previous_role = assoc.role if assoc else None
            next_roles = set(roles_list)
            if assoc and is_admin(previous_role):
                next_roles.add(ADMIN)
            new_role = format_roles(next_roles)
            is_admin_val = is_admin(new_role)

            if assoc:
                assoc.role = new_role
                assoc.is_admin = is_admin_val
            else:
                assoc = UserDatabaseAssociation(
                    user_id=user_id,
                    database_id=database_id,
                    role=new_role,
                    is_admin=is_admin_val
                )
                db.add(assoc)
                
            if previous_role != new_role:
                action = (AuditAction.CHANGE_DATABASE_ROLE if assoc and previous_role
                          else AuditAction.GRANT_DATABASE_ACCESS)
                await log_in(db, actor=admin_user, action=action, target_type=AuditTarget.USER,
                    target_id=user_id, details=DatabaseAccessAuditDetails(
                        operation="change_role" if previous_role else "grant", database_id=database_id,
                        previous_role=previous_role, new_role=new_role), client_ip=client_ip)
            await db.commit()
            
        return {"success": True, "message": f"Successfully associated user {user_id} with database {database_id} as {new_role}."}
