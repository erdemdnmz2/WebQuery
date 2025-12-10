"""
Query Execution Service Layer
Query çalıştırma, analiz etme ve loglama işlemleri
"""
from sqlalchemy.sql import text
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone
from typing import Dict, Any

from query_execution import config
from database_provider import DatabaseProvider
from app_database.app_database import AppDatabase
from app_database.models import User

from query_execution.query_analyzer import QueryAnalyzer

from notification import NotificationService

class QueryService:
    """
    Query execution ve loglama servisi
    
    SQL query'lerini çalıştırır, analiz eder ve sonuçları loglar.
    Admin olmayan kullanıcılar için query güvenlik kontrolü yapar.
    """
    
    def __init__(self, database_provider: DatabaseProvider, app_db: AppDatabase, notification_service: NotificationService):
        """
        QueryService'i başlatır
        
        Args:
            database_provider: Veritabanı bağlantı sağlayıcı
            app_db: Uygulama veritabanı (loglama için)
        """
        self.database_provider = database_provider
        self.app_db = app_db
        self.analyzer = QueryAnalyzer()
        self.notification_service = notification_service

    async def execute_query(self, query: str, user: User, server_name: str, database_name: str) -> Dict[str, Any]:
        """
        SQL query'sini çalıştırır, analiz eder ve loglar
        
        İş Akışı:
            1. Log kaydı oluştur
            2. Query güvenlik analizi yap (admin değilse)
            3. Query'yi çalıştır
            4. Sonuçları limitleyerek döndür
            5. Log'u güncelle (başarılı/hatalı)
        
        Args:
            query: Çalıştırılacak SQL query
            user: Query'yi çalıştıran kullanıcı
            server_name: SQL Server instance adı
            database_name: Hedef veritabanı adı
        
        Returns:
            Dict[str, Any]: {
                "response_type": "data" | "error",
                "data": List[Dict] (query sonuçları),
                "message": str (bilgi mesajı),
                "error": str (hata durumunda)
            }
        
        Note:
            - Admin olmayan kullanıcılar için riskli query'ler engellenir
            - Sonuç satır sayısı MAX_ROW_COUNT_LIMIT ile sınırlandırılır
            - MAX_ROW_COUNT_WARNING aşılırsa warning loglanır
        """
        log_id = None
        try:
            log_id = await self.app_db.create_log(user=user, query=query, machine_name=server_name)
            query_analysis = self.analyzer.analyze(query)
            if not query_analysis["return"] and not user.is_admin:
                error_msg = f"Query rejected: {query_analysis['risk_type']}"
                await self.app_db.update_log(log_id=log_id, successfull=False, error=error_msg)
                try:
                    if self.notification_service:
                        request_time = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
                        await self.notification_service.send_approval_notifivation(
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
                    "error": error_msg
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
 