"""
Query Execution Service Layer
Query execution, analysis and logging operations
"""
from sqlalchemy.sql import text
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone
from typing import Dict, Any

import uuid

from query_execution import config
from database_provider import DatabaseProvider
from app_database.app_database import AppDatabase
from app_database.models import User, QueryData, Workspace

from query_execution.query_analyzer import QueryAnalyzer

from notification import NotificationService

class QueryService:
    """
    Query execution and logging service
    
    Executes SQL queries, analyzes them and logs the results.
    Performs query security check for non-admin users.
    """
    
    def __init__(self, database_provider: DatabaseProvider, app_db: AppDatabase, notification_service: NotificationService):
        """
        Initializes QueryService
        
        Args:
            database_provider: Database connection provider
            app_db: Application database (for logging)
        """
        self.database_provider = database_provider
        self.app_db = app_db
        self.analyzer = QueryAnalyzer()
        self.notification_service = notification_service

    async def execute_query(self, query: str, user: User, server_name: str, database_name: str) -> Dict[str, Any]:
        """
        Executes, analyzes, and logs the SQL query.
        
        Args:
            query: SQL query to execute
            user: User executing the query
            server_name: SQL Server instance name
            database_name: Target database name
        
        Returns:
            Dict[str, Any]: Execution result
        """
        log_id = None
        try:
            log_id = await self.app_db.create_log(user=user, query=query, machine_name=server_name)
            query_analysis = self.analyzer.analyze(query)
            if not query_analysis["return"] and not user.is_admin:
                error_msg = f"Query rejected: {query_analysis['risk_type']}"
                await self.app_db.update_log(log_id=log_id, successfull=False, error=error_msg)
                
                try:
                    async with self.app_db.get_app_db() as db_session:
                        query_uuid = str(uuid.uuid4())
                        query_data = QueryData(
                            user_id=user.id,
                            servername=server_name,
                            database_name=database_name,
                            query=query,
                            uuid=query_uuid,
                            status="waiting_for_approval"
                        )
                        db_session.add(query_data)
                        await db_session.flush()
                        
                        # get ID in context after flush
                        query_data_id = query_data.id
                        
                        workspace_name = f"Pending: {query[:50]}..." if len(query) > 50 else f"Pending: {query}"
                        workspace = Workspace(
                            user_id=user.id,
                            name=workspace_name,
                            description=f"Risk Type: {query_analysis.get('risk_type', 'UNKNOWN')} - Waiting for admin approval",
                            query_id=query_data_id,
                            show_results=None
                        )
                        db_session.add(workspace)
                        await db_session.flush()
                        
                        # get workspace ID after flush
                        workspace_id = workspace.id
                        
                        await db_session.commit()
                        
                    print(f"Query saved for approval - Workspace ID: {workspace_id}, UUID: {query_uuid}")
                except Exception as save_exc:
                    print(f"Failed to save query for approval: {type(save_exc).__name__}: {save_exc}")
                
                try:
                    if self.notification_service:
                        request_time = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
                        await self.notification_service.send_approval_notifivation(
                            request_id=query_uuid,
                            username=getattr(user, 'username', str(getattr(user, 'id', 'unknown'))),
                            request_time=request_time,
                            database_name=database_name,
                            servername=server_name,
                            risk_type=query_analysis.get('risk_type', 'UNKNOWN'),
                            query=query
                        )
                except Exception as notif_exc:
                    print(f"Notification send error: {type(notif_exc).__name__}: {notif_exc}")
                
                return {
                    "response_type": "error",
                    "data": [],
                    "error": f"{error_msg}. Query saved to your workspaces and sent for admin approval."
                }
            async with self.database_provider.get_session(
                user=user,
                servername=server_name,
                database_name=database_name
            ) as session:
                sql_query = text(query)
                result = await session.execute(sql_query)
                rows = result.fetchmany(size=config.MAX_ROW_COUNT_LIMIT)
                row_count = len(rows)
                if row_count > config.MAX_ROW_COUNT_LIMIT:
                    rows = rows[:config.MAX_ROW_COUNT_LIMIT]
                    message = f"{row_count} rows found, showing first {config.MAX_ROW_COUNT_LIMIT}"
                else:
                    message = f"{row_count} rows affected"
                result_data = {
                    "response_type": "data",
                    "data": [dict(row._mapping) for row in rows],
                    "message": message
                }
                await self.app_db.update_log(
                    log_id=log_id,
                    successfull=True,
                    row_count=row_count
                )
                if row_count > config.MAX_ROW_COUNT_WARNING:
                    print(f"Warning: Query returned {row_count} rows")
                return result_data
        except Exception as e:
            error_msg = str(e)
            print(f"Query execution error: {error_msg}")
            if log_id:
                await self.app_db.update_log(
                    log_id=log_id,
                    successfull=False,
                    error=error_msg
                )
            return {
                "response_type": "error",
                "data": [],
                "error": error_msg
            }
 