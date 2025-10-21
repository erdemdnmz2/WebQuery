from app_database.config import DATABASE_URL

from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, AsyncSession, async_sessionmaker
from datetime import datetime
from contextlib import asynccontextmanager
from sqlalchemy.sql import select

from app_database.models import User, actionLogging, loginLogging, queryData, Workspace
from database_provider import DatabaseProvider
from app_database.schemas import UserCreate


class AppDatabase:
    def __init__(self):
        self.app_engine = create_async_engine(
            DATABASE_URL,
            pool_size=20,          # For CRUD operations
            max_overflow=30,       # For peak times
            pool_timeout=20,
            pool_recycle=3600,
            pool_pre_ping=True
        )

        self.AsyncSessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=self.app_engine)

    @asynccontextmanager
    async def get_app_db(self):
        async with self.AsyncSessionLocal() as session:
            try:
                yield session
            finally:
                await session.close()

    async def create_user(db : AsyncSession, user: UserCreate):
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

    async def create_log(self, user: User, query: str, machine_name: str):
        async with self.get_app_db() as db:
            created_log = actionLogging(
                user_id = user.id,
                username = user.username,
                query_date = datetime.now(),
                query = query,
                machine_name = machine_name
            )
            db.add(created_log)
            await db.commit()
            await db.refresh(created_log)
            return created_log
    
    async def update_log(self, log_id, successfull: bool, error : str = None, row_count: int = None):
        async with self.get_app_db() as db:
            result = await db.execute(select(actionLogging).where(actionLogging.id == log_id))
            log = result.scalars().first()

            if not successfull:
                log.ErrorMessage = error
                log.isSuccessfull = False
            else:
                duration = datetime.now() - log.query_date
                log.ExecutionDurationMS = int(duration.total_seconds() * 1000)
                log.isSuccessfull = True
                log.row_count = row_count
            await db.commit()

    async def create_login_log(self, user_id: int, client_ip):
        async with self.get_app_db() as db:
            created_log = loginLogging(
                user_id = user_id,
                login_date = datetime.now(),
                client_ip = client_ip
            )
            db.add(created_log)
            await db.commit()

    async def update_login_log(self, user_id: int):
        async with self.get_app_db() as db:
            result = await db.execute(
                select(loginLogging)
                .where(loginLogging.user_id == user_id)
                .where(loginLogging.logout_date.is_(None))
            )
            log = result.scalars().first()
            if log:
                log.logout_date = datetime.now()
                duration = datetime.now() - log.login_date
                log.login_duration_ms = int(duration.total_seconds() * 1000)
                await db.commit()
            else:
                print(f"Active login record for user {user_id}")
        