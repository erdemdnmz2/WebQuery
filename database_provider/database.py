from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, AsyncSession, async_sessionmaker
from typing import Dict
import os
import  app_database.models as models
from database_provider.config import SERVER_NAMES, create_connection_string, get_master_connection_string
from sqlalchemy.future import select
from contextlib import asynccontextmanager
from sqlalchemy.exc import SQLAlchemyError
from .engine_cache import EngineCache

class DatabaseProvider:
    """
    SQL Server veritabanı bağlantılarını yöneten sınıf.
    Her kullanıcı için ayrı engine cache tutar ve lazy initialization kullanır.
    """
    
    def __init__(self):
        """DatabaseProvider'ı başlatır ve cache yapılarını oluşturur."""
        self.engine_cache: EngineCache = EngineCache()
        self.db_info: Dict[str, list[str]] = {} 

        
    def _create_connection_string(self, username: str, password: str, database: str, server: str, tech: str, driver: str):
        """
        Kullanıcıya özel connection string oluşturur.
        
        Args:
            username: SQL Server kullanıcı adı
            password: SQL Server şifresi
            database: Bağlanılacak veritabanı adı
            server: SQL Server instance adı
            
        Returns:
            str: Formatlanmış connection string
        """
        return create_connection_string(
            tech=tech,
            driver=driver,
            username=username,
            password=password,
            servername=server,
            database=database
        )

    def set_db_info(self, info: Dict[str, list[str]]):
        self.db_info = info
    
    async def get_db_info(self):
        """
        Tüm sunuculardan erişilebilir veritabanlarının listesini alır.
        Master database'e bağlanarak sys.databases tablosunu sorgular.
        System veritabanları (ilk 4) hariç tutulur.
        """
        
        for server in SERVER_NAMES: 
            try:
                master_conn_str = get_master_connection_string(server)
                temp_engine = create_async_engine(master_conn_str)

                async with temp_engine.connect() as connection:
                    results = await connection.execute(text("SELECT name FROM sys.databases"))
                    db_names = results.scalars().all()
                    db_names = db_names[4:]
                    self.db_info[server] = list(db_names)
                    print(f"{server}: {len(db_names)} databases found - {db_names}")

                await temp_engine.dispose()
                temp_engine = None
                
            except Exception as e:
                print(f"Could not connect to {server}: {str(e)}")
                self.db_info[server] = [] 
                
        print(f"Final db_info after processing: {self.db_info}")
    
    @asynccontextmanager
    async def get_session(self, user: models.User, servername: str, database_name: str, tech: str = "mssql", driver: str = "aioodbc"):
        """
        Kullanıcıya özel async database session'ı sağlar (context manager).
        Engine yoksa lazy initialization ile oluşturur.
        
        Args:
            user: Kullanıcı modeli (username ve password içerir)
            server_name: SQL Server instance adı
            database_name: Bağlanılacak veritabanı adı
            tech: Veritabanı teknolojisi (default: mssql)
            driver: Veritabanı sürücüsü (default: aioodbc)
            
        Yields:
            AsyncSession: SQLAlchemy async session
            
        Example:
            async with db_provider.get_session(user, "localhost", "mydb") as session:
                result = await session.execute(query)
        """

        conn_str = create_connection_string(
            tech=tech,
            driver=driver,
            servername=servername,
            database=database_name,
            username=user.username,
            password=user.password,
        )
        
        engine = await self.engine_cache.get_engine(conn_str, owner_id=user.id)

        AsyncSessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine)
        async with AsyncSessionLocal() as session:
            try:
                yield session
            finally:
                await session.close()

    async def close_engines(self):
        """
        Tüm kullanıcıların tüm engine'lerini kapatır ve kaynakları serbest bırakır.
        Uygulama kapanırken çağrılmalıdır.
        """
        await self.engine_cache.stop_loop()

    async def close_user_engines(self, user_id: int):
        """
        Belirli bir kullanıcının tüm engine'lerini kapatır.
        Kullanıcı logout olduğunda çağrılır.
        
        Args:
            user_id: Kapatılacak kullanıcının ID'si
        """
        await self.engine_cache.close_user_engines(user_id) 
    
    def get_db_info_db(self):
        """
        Tüm sunuculardaki veritabanı bilgilerini döndürür.
        
        Returns:
            Dict[str, List[str]]: {server_adı: [veritabanı_adları]}
        """
        return self.db_info