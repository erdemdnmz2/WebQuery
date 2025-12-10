"""
Application Database Manager
Uygulama veritabanı işlemleri (kullanıcı, log, workspace CRUD)
"""
from app_database.config import DATABASE_URL

from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, AsyncSession, async_sessionmaker
from datetime import datetime
from contextlib import asynccontextmanager
from sqlalchemy.sql import select

from app_database.models import User, ActionLogging, LoginLogging, QueryData, Workspace, Base, Databases
from database_provider import DatabaseProvider
from app_database.schemas import UserCreate
from typing import Dict, Any


class AppDatabase:
    """
    Uygulama veritabanı yönetim sınıfı
    
    Kullanıcı yönetimi, query loglama, login loglama ve workspace işlemlerini yapar.
    Connection pool ile optimize edilmiş async database bağlantısı sağlar.
    
    Attributes:
        app_engine: SQLAlchemy async engine (connection pool ile)
        AsyncSessionLocal: Async session factory
    """
    
    def __init__(self):
        """
        AppDatabase'i başlatır ve connection pool'u konfigüre eder
        
        Pool Configuration:
            - pool_size: 20 (normal operasyonlar için)
            - max_overflow: 30 (yoğun zamanlarda ekstra bağlantı)
            - pool_timeout: 20 saniye
            - pool_recycle: 3600 saniye (1 saat)
            - pool_pre_ping: True (bağlantı kontrolü)
        """
        self.app_engine = create_async_engine(
            DATABASE_URL,
            pool_size=20,          
            max_overflow=30,       
            pool_timeout=20,
            pool_recycle=3600,
            pool_pre_ping=True
        )

        self.AsyncSessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=self.app_engine)

    @asynccontextmanager
    async def get_app_db(self):
        """
        Async database session context manager
        
        Yields:
            AsyncSession: SQLAlchemy async session
        
        Example:
            async with app_db.get_app_db() as session:
                result = await session.execute(query)
        """
        async with self.AsyncSessionLocal() as session:
            try:
                yield session
            finally:
                await session.close()

    async def create_tables(self):
        """
        Veritabanında tüm tabloları oluşturur (yoksa)
        Development ortamında kullanılır
        """
        async with self.app_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def create_user(db: AsyncSession, user: UserCreate):
        """
        Yeni kullanıcı oluşturur (static method)
        
        Args:
            db: Async database session
            user: Kullanıcı oluşturma şeması
        
        Returns:
            Dict: {"success": bool, "message": str}
        
        Note:
            Şifre bcrypt ile hash'lenerek saklanır
        """
        created_user = User(
            username = user.username,
            email = user.email
        )
        created_user.set_password(user.password)
        db.add(created_user)
        await db.commit()
        await db.refresh(created_user)
        
        return {
            "success": True,
            "message": "Registration successful! Redirecting to login page..."
        }

    async def create_log(self, user: User, query: str, machine_name: str, approved_execution: bool = False):
        """
        Query execution log'u oluşturur (başlangıç kaydı)
        
        Args:
            user: Query'yi çalıştıran kullanıcı
            query: Çalıştırılan SQL query
            machine_name: SQL Server instance adı
        
        Returns:
            ActionLogging: Oluşturulan log kaydı
        
        Note:
            Log başlangıçta oluşturulur, sonuç update_log ile güncellenir
        """
        async with self.get_app_db() as db:
            async with db.begin():
                created_log = ActionLogging(
                    user_id = user.id,
                    username = user.username,
                    query_date = datetime.now(),
                    query = query,
                    machine_name = machine_name,
                    approved_execution = approved_execution
                )
                db.add(created_log)
                await db.flush()
                await db.refresh(created_log)
                return created_log
    
    async def update_log(self, log_id, successfull: bool, error: str = None, row_count: int = None):
        """
        Query execution log'unu günceller (sonuç kaydı)
        
        Args:
            log_id: Güncellenecek log ID'si
            successfull: Query başarılı mı?
            error: Hata mesajı (başarısızsa)
            row_count: Dönen satır sayısı (başarılıysa)
        
        Note:
            - Başarısızsa: ErrorMessage ve isSuccessfull güncellenir
            - Başarılıysa: ExecutionDurationMS, isSuccessfull ve row_count güncellenir
        """
        async with self.get_app_db() as db:
            async with db.begin():
                result = await db.execute(select(ActionLogging).where(ActionLogging.id == log_id))
                log = result.scalars().first()

                if log:
                    if not successfull:
                        log.ErrorMessage = error
                        log.isSuccessfull = False
                    else:
                        duration = datetime.now() - log.query_date
                        log.ExecutionDurationMS = int(duration.total_seconds() * 1000)
                        log.isSuccessfull = True
                        log.row_count = row_count

    async def create_login_log(self, user_id: int, client_ip):
        """
        Kullanıcı login log'u oluşturur
        
        Args:
            user_id: Giriş yapan kullanıcının ID'si
            client_ip: İstek IP adresi
        
        Note:
            logout_date başlangıçta NULL, logout'ta update_login_log ile güncellenir
        """
        async with self.get_app_db() as db:
            async with db.begin():
                created_log = LoginLogging(
                    user_id = user_id,
                    login_date = datetime.now(),
                    client_ip = client_ip
                )
                db.add(created_log)

    async def update_login_log(self, user_id: int):
        """
        Kullanıcı logout log'unu günceller
        
        Args:
            user_id: Çıkış yapan kullanıcının ID'si
        
        Note:
            - logout_date NULL olan (aktif) log kaydını bulur
            - logout_date ve login_duration_ms günceller
            - Aktif kayıt bulunamazsa warning yazdırır
        """
        async with self.get_app_db() as db:
            async with db.begin():
                result = await db.execute(
                    select(LoginLogging)
                    .where(LoginLogging.user_id == user_id)
                    .where(LoginLogging.logout_date.is_(None))
                )
                log = result.scalars().first()
                if log:
                    log.logout_date = datetime.now()
                    duration = datetime.now() - log.login_date
                    log.login_duration_ms = int(duration.total_seconds() * 1000)
                else:
                    print(f"Active login record for user {user_id}")
        
    async def get_db_info(self) -> Dict[str, Dict[str, Any]]:
        """
        Veritabanı bilgilerini server bazında döndürür.
        Her server için database listesi ve technology bilgisini içerir.
        
        Returns:
            Dict[str, Dict[str, Any]]: {
                servername: {
                    "databases": [database_names],
                    "technology": "mssql" | "mysql" | "postgresql"
                }
            }
        
        Example:
            {
                "localhost": {
                    "databases": ["Northwind", "AdventureWorks"],
                    "technology": "mssql"
                },
                "mysql-server-1": {
                    "databases": ["ecommerce", "analytics"],
                    "technology": "mysql"
                }
            }
        """
        async with self.get_app_db() as db:
            async with db.begin():
                result = await db.execute(
                    select(Databases)
                )
                databases = result.scalars().all()
                db_info : Dict[str, Dict[str, Any]] = {}
                
                for database in databases:
                    servername = database.servername
                    
                    if servername not in db_info:
                        db_info[servername] = {
                            "databases": [],
                            "technology": database.technology
                        }
                    
                    db_info[servername]["databases"].append(database.database_name)                
                return db_info