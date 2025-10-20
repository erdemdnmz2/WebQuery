"""
Query Execution Service Layer
Query çalıştırma, analiz etme ve loglama işlemleri
"""
from sqlalchemy.sql import text
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from typing import Dict, Any

from query_execution import config
from database_provider import DatabaseProvider
from app_database.app_database import AppDatabase
from app_database.models import User



from query_execution.query_analyzer import QueryAnalyzer



class QueryService:
    """Query execution service"""
    def __init__(self, database_provider: DatabaseProvider, app_db: AppDatabase):
        self.database_provider = database_provider
        self.app_db = app_db
        self.analyzer = QueryAnalyzer()

    async def execute_query(self, query: str, user: User, server_name: str, database_name: str) -> Dict[str, Any]:
        log_id = None
        try:
            log = await self.app_db.create_log(user=user, query=query, machine_name=server_name)
            log_id = log.id
            query_analysis = self.analyzer.analyze(query)
            if not query_analysis["return"] and not user.is_admin:
                error_msg = f"Query rejected: {query_analysis['risk_type']}"
                await self.app_db.update_log(log_id=log_id, successfull=False, error=error_msg)
                return {
                    "response_type": "error",
                    "data": [],
                    "error": error_msg
                }
            async with self.database_provider.get_session(
                user=user,
                server_name=server_name,
                database_name=database_name
            ) as session:
                sql_query = text(query)
                result = await session.execute(sql_query)
                rows = result.fetchall()
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
