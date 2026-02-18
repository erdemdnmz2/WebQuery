"""
Application Database Manager
Application database operations (user, log, workspace CRUD)
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
    Application database management class.
    
    Handles user management, logging, and workspace operations.
    Manages async database connections.
    """
    
    def __init__(self):
        """
        Initializes AppDatabase and configures the connection pool.
        """
        self.app_engine = create_async_engine(
            DATABASE_URL,
            pool_size=20,          
            max_overflow=30,       
            pool_timeout=20,
            pool_recycle=3600,
            pool_pre_ping=False
        )

        self.AsyncSessionLocal = async_sessionmaker(autocommit=False, autoflush=True, bind=self.app_engine)

    @asynccontextmanager
    async def get_app_db(self):
        """
        Async database session context manager.
        """
        async with self.AsyncSessionLocal() as session:
            try:
                yield session
            finally:
                await session.close()

    async def create_tables(self):
        """
        Creates all tables in the database if they don't exist.
        """
        async with self.app_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def create_user(db: AsyncSession, user: UserCreate):
        """
        Creates a new user.
        
        Args:
            db: Async database session
            user: User creation schema
        
        Returns:
            Dict: Result message
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
        Creates query execution log (initial record)
        
        Args:
            user: User executing the query
            query: Executed SQL query
            machine_name: SQL Server instance name
        
        Returns:
            ActionLogging: Created log record
        
        Note:
            Log is created initially, result is updated with update_log
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
                log_id = created_log.id
            return log_id
    
    async def update_log(self, log_id, successfull: bool, error: str = None, row_count: int = None):
        """
        Updates query execution log (result record)
        
        Args:
            log_id: Log ID to update
            successfull: Is query successful?
            error: Error message (if failed)
            row_count: Returned row count (if successful)
        
        Note:
            - If failed: ErrorMessage and isSuccessfull are updated
            - If successful: ExecutionDurationMS, isSuccessfull and row_count are updated
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
        Creates user login log
        
        Args:
            user_id: ID of the user logging in
            client_ip: Request IP address
        
        Note:
            logout_date is initially NULL, updated with update_login_log on logout
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
        Updates user logout log
        
        Args:
            user_id: ID of the user logging out
        
        Note:
            - Finds the active log record where logout_date is NULL
            - Updates logout_date and login_duration_ms
            - Prints warning if active record is not found
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
        Returns database information per server.
        Includes database list and technology information for each server.
        
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