"""
Query Execution Service Module
Contains the core QueryService responsible for analyzing, executing, and logging SQL queries.
Strictly typed and documented.
"""
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.future import select
from sqlalchemy.sql import text

from app_database.app_database import AppDatabase
from app_database.models import (
    ApprovalStatus,
    Databases,
    QueryData,
    User,
    UserDatabaseAssociation,
    Workspace,
)
from common.errors import redact_passwords, scrub
from common.exceptions import BaseServiceException
from common.security import mask_result_set
from database_provider import DatabaseProvider
from notification import NotificationService
from query_execution import config
from query_execution.exceptions import QueryAnalysisRejectedError, QueryExecutionError
from query_execution.query_analyzer import QueryAnalyzer

logger = logging.getLogger(__name__)

class QueryService:
    """
    Query execution, security analysis, and logging service.
    Coordinates risk analysis and target database execution under strict auditing.
    """
    
    database_provider: DatabaseProvider
    app_db: AppDatabase
    analyzer: QueryAnalyzer
    notification_service: NotificationService

    def __init__(self, database_provider: DatabaseProvider, app_db: AppDatabase, notification_service: NotificationService) -> None:
        """
        Initializes the QueryService with required providers.
        
        Args:
            database_provider: The target database connections provider.
            app_db: The application metadata database manager.
            notification_service: The notifications service.
        """
        self.database_provider = database_provider
        self.app_db = app_db
        self.analyzer = QueryAnalyzer()
        self.notification_service = notification_service

    async def execute_query(
        self,
        query: str,
        user: User,
        db_uuid: str,
        ad_hoc_mask_columns: list[str] | None = None,
        client_ip: str | None = None,
    ) -> dict[str, Any]:
        """
        Analyzes, logs, and executes the SQL query against the target database.
        If the query is identified as risky, it is routed for admin approval.
        
        Args:
            query: The SQL query to analyze and execute.
            user: The authenticated user executing the query.
            db_uuid: The target database unique identifier.
            ad_hoc_mask_columns: Temporary columns to mask for this transaction (optional).
            client_ip: Originating client IP address for audit logging (optional).
            
        Returns:
            Dict[str, Any]: The execution results, rows, or error details.
        """
        log_id: int | None = None
        query_uuid: str = str(uuid.uuid4())
        try:
            if db_uuid not in self.database_provider.db_by_uuid:
                raise BaseServiceException(f"Database with UUID '{db_uuid}' not found.")
            db_entry = self.database_provider.db_by_uuid[db_uuid]
            server_name = db_entry["servername"]
            database_name = db_entry["database_name"]
            technology = db_entry["technology"]

            logger.info(f"Initiating query execution on server '{server_name}', database '{database_name}'")

            # Resolve database_id for audit logging
            db_id = None
            masking_cols = set()
            user_role = "READER"  # Default fallback role
            
            async with self.app_db.get_app_db() as db_session:
                db_result = await db_session.execute(
                    select(Databases).where(Databases.uuid == db_uuid)
                )
                db_entry_model = db_result.scalars().first()
                if not db_entry_model:
                    raise BaseServiceException("Target database does not exist in registry.")
                db_id = db_entry_model.id

                assoc_result = await db_session.execute(
                    select(UserDatabaseAssociation).where(
                        UserDatabaseAssociation.user_id == user.id,
                        UserDatabaseAssociation.database_id == db_id
                    )
                )
                assoc = assoc_result.scalars().first()
                if not assoc:
                    raise QueryAnalysisRejectedError("You do not have permission to access this database.")
                user_role = assoc.role

            # Role capability verification using SQLGlot AST analyzer
            if not self.analyzer.check_permissions_match_role(query, user_role, technology=technology):
                raise QueryAnalysisRejectedError(
                    message=f"Query blocked: Your role '{user_role}' is not authorized to execute this query."
                )
            
            if db_id:
                rules = await self.app_db.get_masking_rules(db_id)
                for rule in rules:
                    masking_cols.add(rule.column_name.lower())
            
            if ad_hoc_mask_columns:
                for col in ad_hoc_mask_columns:
                    masking_cols.add(col.lower())

            is_db_admin = "ADMIN" in [r.strip().upper() for r in user_role.split(",")]
            query_analysis: dict[str, Any] = self.analyzer.analyze(query, technology=technology)
            risk_level: str | None = query_analysis.get("risk_type")

            # Create the initial audit log now that we have all context
            log_id = await self.app_db.create_log(
                user=user,
                query=query,
                machine_name=server_name,
                approval_status=ApprovalStatus.AUTO_APPROVED,
                database_id=db_id,
                trace_id=query_uuid,
                client_ip=client_ip,
                risk_level=risk_level,
            )

            if not query_analysis["return"] and not is_db_admin:
                error_msg: str = f"Query rejected: {query_analysis['risk_type']}"
                await self.app_db.update_log(log_id=log_id, successfull=False, error=error_msg)
                # Mark the log as pending admin approval
                await self.app_db.update_approval_status(
                    trace_id=query_uuid,
                    approval_status=ApprovalStatus.PENDING,
                )
                
                try:
                    async with self.app_db.get_app_db() as db_session:
                        query_data: QueryData = QueryData(
                            user_id=user.id,
                            servername=server_name,
                            database_name=database_name,
                            query=query,
                            uuid=query_uuid,
                            status="waiting_for_approval",
                            risk_type=query_analysis.get('risk_type')
                        )
                        db_session.add(query_data)
                        await db_session.flush()
                        
                        query_data_id: int = query_data.id
                        
                        workspace_name: str = f"Pending: {query[:50]}..." if len(query) > 50 else f"Pending: {query}"
                        workspace: Workspace = Workspace(
                            user_id=user.id,
                            name=workspace_name,
                            description=f"Risk Type: {query_analysis.get('risk_type', 'UNKNOWN')} - Waiting for admin approval",
                            query_id=query_data_id,
                            show_results=None
                        )
                        db_session.add(workspace)
                        await db_session.flush()
                        
                        workspace_id: int = workspace.id
                        await db_session.commit()
                        
                    logger.info(f"Query saved for approval - Workspace ID: {workspace_id}, UUID: {query_uuid}")
                except Exception as save_exc:
                    logger.error(f"Failed to save query for approval: {type(save_exc).__name__}: {save_exc}")
                
                try:
                    if self.notification_service:
                        request_time: str = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
                        await self.notification_service.send_approval_notification(
                             request_id=query_uuid,
                             username=getattr(user, 'username', str(getattr(user, 'id', 'unknown'))),
                             request_time=request_time,
                             database_name=database_name,
                             servername=server_name,
                             risk_type=query_analysis.get('risk_type', 'UNKNOWN'),
                             query=query
                        )
                except Exception as notif_exc:
                    logger.error(f"Notification send error: {type(notif_exc).__name__}: {notif_exc}")
                
                raise QueryAnalysisRejectedError(
                    message=f"{error_msg}. Query saved to your workspaces and sent for admin approval."
                )
                
            async with self.database_provider.get_session(
                user=user,
                db_uuid=db_uuid
            ) as session:
                sql_query = text(query)
                result = await session.execute(sql_query)
                
                row_count: int = 0
                message: str = ""
                result_data: dict[str, Any] = {}
                
                if result.returns_rows:
                    rows = result.fetchmany(size=config.MAX_ROW_COUNT_LIMIT)
                    row_count = len(rows)
                    if row_count >= config.MAX_ROW_COUNT_LIMIT:
                        message = f"Truncated to MAX_ROW_COUNT_LIMIT ({config.MAX_ROW_COUNT_LIMIT})"
                    else:
                        message = f"{row_count} rows returned"
                    
                    raw_data = [dict(row._mapping) for row in rows]
                    if not is_db_admin and masking_cols:
                        raw_data = mask_result_set(raw_data, masking_cols)
                        
                    result_data = {
                        "response_type": "data",
                        "data": raw_data,
                        "message": message
                    }
                else:
                    row_count = result.rowcount if result.rowcount is not None else 0
                    message = f"{row_count} rows affected"
                    result_data = {
                        "response_type": "data",
                        "data": [],
                        "message": message
                    }
                
                applied_rules_str = json.dumps(list(masking_cols)) if masking_cols else None
                await self.app_db.update_log(
                    log_id=log_id,
                    successfull=True,
                    row_count=row_count,
                    applied_masking_rules=applied_rules_str
                )
                
                if row_count > config.MAX_ROW_COUNT_WARNING:
                    logger.warning(f"Query returned high row count: {row_count} rows")
                
                logger.info(f"Query executed successfully. Result: {message}")
                return result_data
                
        except BaseServiceException:
            # Re-raise already translated service exceptions
            raise
        except Exception as e:
            error_msg: str = str(e)
            safe_log_error = redact_passwords(error_msg)
            logger.error(
                "Query execution failed [%s]: %s",
                type(e).__name__,
                safe_log_error,
            )
            if log_id:
                await self.app_db.update_log(
                    log_id=log_id,
                    successfull=False,
                    error=safe_log_error
                )
            raise QueryExecutionError(scrub(error_msg), original_exception=e)

    async def get_active_masking_rules(self, db_uuid: str) -> list[str]:
        """
        Retrieves column names that are persistently masked for a given database UUID.
        """
        async with self.app_db.get_app_db() as db:
            db_result = await db.execute(
                select(Databases).where(Databases.uuid == db_uuid)
            )
            db_entry = db_result.scalars().first()
            if not db_entry:
                return []
            
            rules = await self.app_db.get_masking_rules(db_entry.id)
            return [r.column_name.lower() for r in rules]
