"""
Database Provider Module
Manages database engines caching and session provisioning using centralized credentials.
All functions and classes are strictly typed.
"""
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

from app_database import models
from database_provider.config import (
    CENTRAL_DB_PASSWORD,
    CENTRAL_DB_USER,
    QUERY_TIMEOUT_SECONDS,
    SESSION_INIT_SQL,
    create_connection_string,
    get_connect_args,
    get_driver_for_technology,
)

from .engine_cache import EngineCache


class DatabaseProvider:
    """
    Manages SQL Server database connections.
    """
    
    def __init__(self):
        """Initializes DatabaseProvider."""
        self.engine_cache: EngineCache = EngineCache()
        self.db_info: dict[str, dict[str, Any]] = {}
        # Flat dictionary mapping db_uuid -> database details for O(1) lookup
        self.db_by_uuid: dict[str, dict[str, Any]] = {}

    def set_db_info(self, info: dict[str, dict[str, Any]]) -> None:
        """
        Sets database configuration information and builds UUID lookup dictionary.
        
        Args:
            info: Database configuration dictionary.
        """
        print(f"[DEBUG set_db_info] Input info: {info}")
        self.db_info = info
        self.db_by_uuid = {}
        for servername, server_data in info.items():
            tech = server_data.get("technology", "mssql")
            for db_data in server_data.get("databases", []):
                # db_data is {"name": "db_name", "uuid": "db_uuid"}
                print(f"[DEBUG set_db_info] Processing db_data: {db_data}")
                if isinstance(db_data, dict) and "uuid" in db_data:
                    db_uuid = db_data["uuid"]
                    self.db_by_uuid[db_uuid] = {
                        "servername": servername,
                        "database_name": db_data["name"],
                        "technology": tech
                    }
        print(f"[DEBUG set_db_info] Built db_by_uuid: {self.db_by_uuid}")
    
    @asynccontextmanager
    async def get_session(self, user: models.User, db_uuid: str):
        """
        Provides user-specific async database session using centralized credentials.
        
        Args:
            user: User model.
            db_uuid: Database unique identifier.
            
        Yields:
            AsyncSession: SQLAlchemy async session.
        """
        
        # Validation
        if db_uuid not in self.db_by_uuid:
            raise ValueError(
                f"Database with UUID '{db_uuid}' not found in configuration."
            )
        
        db_entry = self.db_by_uuid[db_uuid]
        servername = db_entry["servername"]
        database_name = db_entry["database_name"]
        tech = db_entry["technology"]
        driver = get_driver_for_technology(tech)
 
        conn_str = create_connection_string(
            tech=tech,
            driver=driver,
            servername=servername,
            database=database_name,
            username=CENTRAL_DB_USER,
            password=CENTRAL_DB_PASSWORD,
        )
        
        engine = await self.engine_cache.get_engine(
            conn_str,
            db_uuid=db_uuid,
            connect_args=get_connect_args(tech, QUERY_TIMEOUT_SECONDS),
        )

        AsyncSessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine)
        async with AsyncSessionLocal() as session:
            try:
                init_sql = SESSION_INIT_SQL.get(tech.lower().strip())
                if init_sql:
                    await session.execute(
                        text(init_sql.format(ms=QUERY_TIMEOUT_SECONDS * 1000))
                    )
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
    
    def get_db_info_db(self) -> dict[str, dict[str, Any]]:
        """
        Returns database configuration information for all servers.
        
        Returns:
            Dict[str, Dict[str, Any]]: Configuration mapping of servers to their databases and technology.
        """
        return self.db_info
