"""Target database session provisioning with per-database role credentials."""
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
        # Keep the public database catalogue separate from credential-bearing
        # runtime entries. ``get_db_info_db`` feeds an API response.
        self.db_info = {}
        self.db_by_uuid = {}
        for servername, server_data in info.items():
            tech = server_data.get("technology", "mssql")
            public_databases = []
            for db_data in server_data.get("databases", []):
                # db_data is {"name", "uuid", "connection_mode", "credentials"}
                if isinstance(db_data, dict) and "uuid" in db_data:
                    # The ORM hands back uuid.UUID for MSSQL UNIQUEIDENTIFIER, while every
                    # lookup arrives as a string from the request body. Normalise to str
                    # so db_by_uuid stays keyed the way its Dict[str, ...] type declares.
                    db_uuid = str(db_data["uuid"])
                    self.db_by_uuid[db_uuid] = {
                        "servername": servername,
                        "database_name": db_data["name"],
                        "technology": tech,
                        "credentials": db_data.get("credentials", {}),
                    }
                    # The connection mode is derived state, not a secret: it
                    # says which tiers exist, never who they authenticate as.
                    public_databases.append({
                        "name": db_data["name"],
                        "uuid": db_uuid,
                        "connection_mode": db_data.get("connection_mode"),
                    })
            self.db_info[servername] = {
                "databases": public_databases,
                "technology": tech,
            }

    def _credentials_for(self, db_uuid: str, tier: str) -> tuple[str, str] | None:
        """Resolve one selected tier without exposing credentials to callers."""
        credentials = self.db_by_uuid[db_uuid].get("credentials", {})
        tier_credentials = credentials.get(tier, {})
        username = tier_credentials.get("username")
        password = tier_credentials.get("password")
        if username and password:
            return username, password

        # Existing registered databases are migrated incrementally. They have
        # no tier credentials at all and retain the old central connection only
        # until an administrator re-registers them with a supported mode.
        has_any_tier_credential = any(
            values.get("username") or values.get("password")
            for values in credentials.values()
        )
        if not has_any_tier_credential and tier in {"ro", "rw"}:
            return CENTRAL_DB_USER, CENTRAL_DB_PASSWORD
        return None
    
    @asynccontextmanager
    async def get_session(self, user: models.User, db_uuid: str, tier: str = "ro"):
        """
        Provides an async target database session for the requested tier.
        
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
        
        if tier not in {"ro", "rw", "ddl"}:
            raise ValueError(f"Unsupported credential tier '{tier}'.")

        db_entry = self.db_by_uuid[db_uuid]
        servername = db_entry["servername"]
        database_name = db_entry["database_name"]
        tech = db_entry["technology"]
        driver = get_driver_for_technology(tech)
 
        credentials = self._credentials_for(db_uuid, tier)
        if credentials is None:
            raise ValueError(
                f"Bu veritabanı için {tier.upper()} kademesinde kimlik bilgisi tanımlı değil."
            )
        username, password = credentials
        conn_str = create_connection_string(
            tech=tech,
            driver=driver,
            servername=servername,
            database=database_name,
            username=username,
            password=password,
        )
        
        engine = await self.engine_cache.get_engine(
            conn_str,
            db_uuid=db_uuid,
            tier=tier,
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

    async def close_database_engines(self, db_uuid: str) -> int:
        """
        Closes all cached role-tier engines for one target database.
        """
        return await self.engine_cache.close_database_engines(db_uuid)

    def get_db_info_db(self) -> dict[str, dict[str, Any]]:
        """
        Returns database configuration information for all servers.
        
        Returns:
            Dict[str, Dict[str, Any]]: Configuration mapping of servers to their databases and technology.
        """
        return self.db_info
