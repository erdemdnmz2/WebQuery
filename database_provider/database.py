from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, AsyncSession, async_sessionmaker
from typing import Dict, Any
import os
import  app_database.models as models
from database_provider.config import (
    SERVER_NAMES, 
    create_connection_string, 
    get_master_connection_string,
    get_driver_for_technology
)
from sqlalchemy.future import select
from contextlib import asynccontextmanager
from sqlalchemy.exc import SQLAlchemyError
from .engine_cache import EngineCache

class DatabaseProvider:
    """
    Manages SQL Server database connections.
    """
    
    def __init__(self):
        """Initializes DatabaseProvider."""
        self.engine_cache: EngineCache = EngineCache()
        self.db_info: Dict[str, Dict[str, Any]] = {}
        # Format: {servername: {"databases": [list], "technology": str}}

    def set_db_info(self, info: Dict[str, Dict[str, Any]]):
        """
        Sets database configuration information.
        
        Args:
            info: Database configuration dictionary
        """
        self.db_info = info
    
    @asynccontextmanager
    async def get_session(self, user: models.User, servername: str, database_name: str):
        """
        Provides user-specific async database session.
        
        Args:
            user: User model
            servername: Server instance name
            database_name: Target database name
            
        Yields:
            AsyncSession: SQLAlchemy async session
        """
        
        # Server validation
        if servername not in self.db_info:
            raise ValueError(
                f"Server '{servername}' not found in database configuration. "
                f"Available servers: {list(self.db_info.keys())}. "
                f"Please add it to the Databases table."
            )
        
        server_info = self.db_info[servername]
        
        # Database validation
        available_databases = server_info.get("databases", [])
        if database_name not in available_databases:
            raise ValueError(
                f"Database '{database_name}' not found for server '{servername}'. "
                f"Available databases: {available_databases}. "
                f"Please add it to the Databases table."
            )
        
        # Get technology and driver
        tech = server_info.get("technology", "mssql")
        driver = get_driver_for_technology(tech)

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
            Dict[str, Dict[str, Any]]: {
                servername: {
                    "databases": [database_names],
                    "technology": str
                }
            }
        """
        return self.db_info