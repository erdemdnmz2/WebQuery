"""
Application Database Manager
Application database operations (user, log, workspace CRUD)
"""
from contextlib import asynccontextmanager
from datetime import datetime
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.sql import select

from common.roles import mode_from_credentials

from .config import DATABASE_URL
from .models import (
    ActionLogging,
    ApprovalStatus,
    Base,
    BlacklistedToken,
    Databases,
    LoginLogging,
    MaskingRule,
    User,
)
from .schemas import UserCreate

logger = logging.getLogger(__name__)


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
        kwargs = {
            "pool_pre_ping": False
        }
        
        if not DATABASE_URL.startswith("sqlite"):
            kwargs.update({
                "pool_size": 20,
                "max_overflow": 30,
                "pool_timeout": 20,
                "pool_recycle": 3600
            })

        self.app_engine = create_async_engine(
            DATABASE_URL,
            **kwargs
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

    async def create_user(self, db: AsyncSession, user: UserCreate):
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

    async def create_log(
        self,
        user: User,
        query: str,
        machine_name: str,
        approval_status: ApprovalStatus = ApprovalStatus.AUTO_APPROVED,
        database_id: int | None = None,
        trace_id: str | None = None,
        client_ip: str | None = None,
        risk_level: str | None = None,
        approved_execution: bool = False,
    ) -> int:
        """
        Creates query execution log (initial record).

        Args:
            user: User executing the query.
            query: Executed SQL query.
            machine_name: SQL Server instance name.
            approval_status: Initial approval state (default: auto_approved).
            database_id: Target database FK for join queries.
            trace_id: UUID linking this log to QueryData for Slack approval lookup.
            client_ip: Originating client IP address.
            risk_level: Risk type string from QueryAnalyzer.
            approved_execution: Legacy boolean flag (kept for backward compatibility).

        Returns:
            int: ID of the created log record.
        """
        async with self.get_app_db() as db:
            async with db.begin():
                created_log = ActionLogging(
                    user_id=user.id,
                    username=user.username,
                    query_date=datetime.now(),
                    query=query,
                    machine_name=machine_name,
                    approved_execution=approved_execution,
                    approval_status=approval_status,
                    database_id=database_id,
                    trace_id=trace_id,
                    client_ip=client_ip,
                    risk_level=risk_level,
                )
                db.add(created_log)
                await db.flush()
                log_id = created_log.id
            return log_id
    
    async def update_log(
        self,
        log_id: int,
        successfull: bool,
        error: str | None = None,
        row_count: int | None = None,
        applied_masking_rules: str | None = None,
    ):
        """
        Updates query execution log (result record).

        Args:
            log_id: Log ID to update.
            successfull: Is query successful?
            error: Error message (if failed).
            row_count: Returned row count (if successful).
            applied_masking_rules: JSON string of applied masking rules (optional).

        Note:
            - If failed: ErrorMessage and isSuccessfull are updated.
            - If successful: ExecutionDurationMS, isSuccessfull and row_count are updated.
        """
        async with self.get_app_db() as db, db.begin():
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
                    if applied_masking_rules:
                        log.applied_masking_rules = applied_masking_rules

    async def update_approval_status(
        self,
        trace_id: str,
        approval_status: ApprovalStatus,
        approved_by: str | None = None,
        approved_by_slack_id: str | None = None,
    ) -> bool:
        """
        Updates approval status on the ActionLogging record matched by trace_id.
        Called by SlackListener after admin approves or rejects a query.

        Args:
            trace_id: UUID linking ActionLogging to QueryData (set at log creation).
            approval_status: New approval status (APPROVED or REJECTED).
            approved_by: WebQuery username or Slack email fallback.
            approved_by_slack_id: Immutable Slack user ID.

        Returns:
            bool: True if record was found and updated, False otherwise.
        """
        async with self.get_app_db() as db, db.begin():
            result = await db.execute(
                select(ActionLogging).where(ActionLogging.trace_id == trace_id)
            )
            log = result.scalars().first()
            if not log:
                return False

            log.approval_status = approval_status
            log.approved_execution = (approval_status == ApprovalStatus.APPROVED)
            log.approved_by = approved_by
            log.approved_by_slack_id = approved_by_slack_id
            log.approved_at = datetime.now()
            return True

    async def create_login_log(self, user_id: int, client_ip):
        """
        Creates user login log
        
        Args:
            user_id: ID of the user logging in
            client_ip: Request IP address
        
        Note:
            logout_date is initially NULL, updated with update_login_log on logout
        """
        async with self.get_app_db() as db, db.begin():
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
        async with self.get_app_db() as db, db.begin():
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
                logger.warning("Aktif giriş kaydı bulunamadı: kullanıcı_id=%d", user_id)
        
    async def get_db_info(self) -> dict[str, dict[str, Any]]:
        """
        Returns registered target databases grouped by server.

        Each database carries its connection mode and its per-tier credentials.
        The credentials are for runtime connection building only;
        ``DatabaseProvider.set_db_info`` splits them off before anything that
        reaches an API response.

        Returns:
            Dict[str, Dict[str, Any]]: {
                servername: {
                    "technology": "mssql" | "mysql" | "postgresql",
                    "databases": [{
                        "name": str,
                        "uuid": str,
                        "connection_mode": "ro" | "ro_rw" | "ro_rw_ddl" | None,
                        "credentials": {tier: {"username": str, "password": str}},
                    }]
                }
            }
        """
        async with self.get_app_db() as db, db.begin():
            result = await db.execute(
                select(Databases)
            )
            databases = result.scalars().all()
            db_info : dict[str, dict[str, Any]] = {}
            
            for database in databases:
                servername = database.servername
                if servername not in db_info:
                    db_info[servername] = {
                        "databases": [],
                        "technology": database.technology
                    }
                db_info[servername]["databases"].append({
                    "name": database.database_name,
                    "uuid": database.uuid,
                    "connection_mode": mode_from_credentials(
                        has_ro=bool(database.username_ro and database.password_ro),
                        has_rw=bool(database.username_rw and database.password_rw),
                        has_ddl=bool(database.username_ddl and database.password_ddl),
                    ),
                    "credentials": {
                        "ro": {"username": database.username_ro, "password": database.password_ro},
                        "rw": {"username": database.username_rw, "password": database.password_rw},
                        "ddl": {"username": database.username_ddl, "password": database.password_ddl},
                    },
                })
            return db_info

    async def blacklist_token(self, jti: str, expires_at: datetime) -> None:
        """
        Registers a new blacklisted JTI token upon user logout.
        """
        async with self.get_app_db() as db, db.begin():
            blacklisted = BlacklistedToken(jti=jti, expires_at=expires_at)
            db.add(blacklisted)

    async def is_token_blacklisted(self, jti: str) -> bool:
        """
        Checks if a JTI token has been blacklisted.
        """
        async with self.get_app_db() as db:
            result = await db.execute(
                select(BlacklistedToken).where(BlacklistedToken.jti == jti)
            )
            blacklisted = result.scalars().first()
            return blacklisted is not None

    async def get_masking_rules(self, database_id: int) -> list[MaskingRule]:
        """
        Retrieves active masking rules for a specific database.
        """
        async with self.get_app_db() as db:
            result = await db.execute(
                select(MaskingRule).where(MaskingRule.database_id == database_id, MaskingRule.is_active == True)
            )
            return list(result.scalars().all())
