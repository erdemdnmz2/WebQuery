"""
Database Provider Module
Manages database engines caching and session provisioning using centralized credentials.
All functions and classes are strictly typed.
"""
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, AsyncSession, async_sessionmaker
from typing import Dict, Any
import os
import  app_database.models as models
from database_provider.config import (
    SERVER_NAMES, 
    create_connection_string, 
    get_master_connection_string,
    get_driver_for_technology,
    DB_USER,
    DB_PASSWORD
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

    def set_db_info(self, info: Dict[str, Dict[str, Any]]) -> None:
        """
        Sets database configuration information.
        
        Args:
            info: Database configuration dictionary.
        """
        self.db_info = info
    
    @asynccontextmanager
    async def get_session(self, user: models.User, servername: str, database_name: str):
        """
        Provides user-specific async database session using centralized credentials.
        
        Args:
            user: User model.
            servername: Server instance name.
            database_name: Target database name.
            
        Yields:
            AsyncSession: SQLAlchemy async session.
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
            username=DB_USER,
            password=DB_PASSWORD,
        )
        
        engine = await self.engine_cache.get_engine(conn_str, owner_id=user.id)

        AsyncSessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine)
        async with AsyncSessionLocal() as session:
            try:
                yield session
            finally:
                await session.close()

    async def start_cache_loop(self) -> None:
        """
        Starts the background engine cache cleanup loop.
        Should be called during application startup.
        """
        await self.engine_cache.start_loop()

    async def close_engines(self) -> None:
        """
        Closes all engines for all users and releases resources.
        Should be called when the application shuts down.
        """
        await self.engine_cache.stop_loop()

    async def close_user_engines(self, user_id: int) -> None:
        """
        Closes all database engines for a specific user.
        Called when a user logs out.
        
        Args:
            user_id: The ID of the user whose engines should be closed.
        """
        await self.engine_cache.close_user_engines(user_id) 
    
    def get_db_info_db(self) -> Dict[str, Dict[str, Any]]:
        """
        Returns database configuration information for all servers.
        
        Returns:
            Dict[str, Dict[str, Any]]: Configuration mapping of servers to their databases and technology.
        """
        return self.db_info