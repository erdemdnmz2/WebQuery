from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, AsyncSession, async_sessionmaker
from typing import Dict
import os
import  app_database.models as models
from database_provider.config import SERVER_NAMES, create_connection_string, get_master_connection_string
from sqlalchemy.future import select
from contextlib import asynccontextmanager
from sqlalchemy.exc import SQLAlchemyError
from engine_cache import EngineCache

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
    async def get_session(self, user: models.User, server_name: str, database_name: str):
        """
        Kullanıcıya özel async database session'ı sağlar (context manager).
        Engine yoksa lazy initialization ile oluşturur.
        
        Args:
            user: Kullanıcı modeli (username ve password içerir)
            server_name: SQL Server instance adı
            database_name: Bağlanılacak veritabanı adı
            
        Yields:
            AsyncSession: SQLAlchemy async session
            
        Example:
            async with db_provider.get_session(user, "localhost", "mydb") as session:
                result = await session.execute(query)
        """
        if self.engine_cache[user.id][server_name][database_name] is None:
            conn_str = self._create_connection_string(
                username=user.username, 
                password=user.password, 
                database=database_name,
                server=server_name
            )
            self.engine_cache[user.id][server_name][database_name] = create_async_engine(
                conn_str,
                pool_size=1,
                max_overflow=1,
                pool_timeout=30,
                pool_recycle=1800,
                pool_pre_ping=True
            )
        
        engine = self.engine_cache[user.id][server_name][database_name]
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
        for user_id in self.engine_cache.keys():
            for server_name in self.engine_cache[user_id].keys():
                for database_name in self.engine_cache[user_id][server_name].keys():
                    engine = self.engine_cache[user_id][server_name][database_name]
                    if engine is not None:
                        await engine.dispose()
                        self.engine_cache[user_id][server_name][database_name] = None

    async def close_user_engines(self, user_id: int):
        """
        Belirli bir kullanıcının tüm engine'lerini kapatır.
        Kullanıcı logout olduğunda çağrılır.
        
        Args:
            user_id: Kapatılacak kullanıcının ID'si
        """
        if user_id in self.engine_cache:
            for server_name in self.engine_cache[user_id]:
                for db_name in self.engine_cache[user_id][server_name]:
                    engine = self.engine_cache[user_id][server_name][db_name]
                    if engine is not None:
                        await engine.dispose()
            self.engine_cache.pop(user_id, None) 

    async def add_user_to_cache(self, user_id: int, username: str, password: str):
        """
        Yeni kullanıcıyı cache'e ekler ve erişebileceği tüm veritabanları için 
        engine placeholder'ları oluşturur (lazy initialization).
        
        Args:
            user_id: Kullanıcı ID'si
            username: SQL Server kullanıcı adı
            password: SQL Server şifresi
        """
        self.engine_cache[user_id] = {}
        for server_name, databases in self.db_info.items():
            self.engine_cache[user_id][server_name] = {}
            for db_name in databases:
                conn_str = self._create_connection_string(username, password, db_name, server_name)
                self.engine_cache[user_id][server_name][db_name] = None  # Lazy initialization
    
    def get_db_info_db(self):
        """
        Tüm sunuculardaki veritabanı bilgilerini döndürür.
        
        Returns:
            Dict[str, List[str]]: {server_adı: [veritabanı_adları]}
        """
        return self.db_info