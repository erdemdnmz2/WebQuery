"""
Application Database Models
SQLAlchemy ORM models for the application database
"""
import enum
import logging
import os
import re
import uuid

import anyio.to_thread
import bcrypt
from cryptography.fernet import Fernet, MultiFernet
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    event,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy import false as sql_false
from sqlalchemy import true as sql_true
from sqlalchemy.dialects.mssql import DATETIME2, NVARCHAR, UNIQUEIDENTIFIER, VARCHAR
from sqlalchemy.dialects.mssql import TEXT as MSSQL_TEXT
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.types import TypeDecorator

from common.clock import db_now
from common.roles import ADMIN
from common.roles import parse as parse_roles

Base = declarative_base()

logger = logging.getLogger(__name__)

# A deliberate cost choice: expensive enough that an offline attack on a leaked
# hash is impractical. The cost is real (1-2s of CPU per call), which is exactly
# why hashing runs on a worker thread rather than the event loop.
BCRYPT_ROUNDS = 14

# A valid bcrypt hash of a value nobody holds. Verifying against it makes a
# login for an unknown address cost the same as one for a known address.
# Without it the two answered at very different speeds — instant versus ~1.5s —
# which turns the login endpoint into an email-enumeration oracle regardless of
# how carefully the response body is worded.
_DUMMY_HASH = bcrypt.hashpw(b"webquery-timing-equaliser", bcrypt.gensalt(rounds=BCRYPT_ROUNDS))


def validate_password_policy(plain_password: str) -> None:
    """Raise ValueError unless the password meets the B2B policy."""
    if len(plain_password) < 12:
        raise ValueError("Şifre en az 12 karakter olmalıdır.")
    if not re.search(r'[A-Z]', plain_password) or not re.search(r'[0-9]', plain_password):
        raise ValueError("Şifre en az bir büyük harf ve bir rakam içermelidir.")


def hash_password(plain_password: str) -> str:
    """Hash a password. Blocking; call it through a worker thread."""
    return bcrypt.hashpw(
        plain_password.encode("utf-8"), bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
    ).decode("utf-8")


_hash_password = hash_password  # internal alias used by User.aset_password


def _verify_password(plain_password: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed.encode("utf-8"))


async def burn_password_check() -> None:
    """Spend the same CPU a real verification would, and discard the result.

    Called when no user matches the submitted address, so the response time of
    a miss is indistinguishable from that of a wrong password.
    """
    await anyio.to_thread.run_sync(
        bcrypt.checkpw, b"webquery-timing-equaliser-miss", _DUMMY_HASH
    )


class ApprovalStatus(str, enum.Enum):
    """
    Approval status for query execution log entries.
    """
    AUTO_APPROVED = "auto_approved"  # Low risk, passed automatically
    PENDING       = "pending"        # Waiting for admin approval
    APPROVED      = "approved"       # Approved by admin
    REJECTED      = "rejected"       # Rejected by admin

# Define cross-db compatible types
AppDateTime = DateTime().with_variant(DATETIME2(precision=7), "mssql")
AppVarChar = String().with_variant(VARCHAR(length=None), "mssql")
AppNVarChar = String().with_variant(NVARCHAR(length=None), "mssql")
AppText = Text().with_variant(MSSQL_TEXT(), "mssql")
AppUUID = String(36).with_variant(UNIQUEIDENTIFIER(), "mssql")

class EncryptedText(TypeDecorator):
    """
    SQLAlchemy TypeDecorator that transparently encrypts and decrypts text at rest using AES (Fernet).

    Reads ``QUERY_ENCRYPTION_KEYS`` (comma-separated, newest first) when set, or
    falls back to the single ``QUERY_ENCRYPTION_KEY`` for existing deployments.
    Encryption always uses the first key; decryption tries every key in order,
    which is what makes rotation possible: put the new key first, keep the old
    one in the list, re-save each row once (or let it happen naturally), then
    drop the old key once nothing decrypts with it anymore.
    """
    impl = Text

    _fernet: MultiFernet | None = None

    @classmethod
    def _get_fernet(cls) -> MultiFernet:
        if cls._fernet is None:
            keys_csv = os.getenv("QUERY_ENCRYPTION_KEYS")
            raw_keys = (
                [key.strip() for key in keys_csv.split(",") if key.strip()]
                if keys_csv
                else [os.getenv("QUERY_ENCRYPTION_KEY") or ""]
            )
            if not raw_keys or not raw_keys[0]:
                raise RuntimeError(
                    "QUERY_ENCRYPTION_KEY(S) tanımlı değil. Şifreleme yapılamaz."
                )
            cls._fernet = MultiFernet([Fernet(key) for key in raw_keys])
        return cls._fernet

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        fernet = self._get_fernet()
        encrypted_bytes = fernet.encrypt(value.encode("utf-8"))
        return encrypted_bytes.decode("utf-8")

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        fernet = self._get_fernet()
        try:
            decrypted_bytes = fernet.decrypt(value.encode("utf-8"))
            return decrypted_bytes.decode("utf-8")
        except Exception:
            # A value that fails every configured key falls back to being
            # returned raw, so a pre-encryption row or a plaintext migration
            # artifact does not take the whole read down. That fallback used to
            # be silent: if QUERY_ENCRYPTION_KEY(S) is ever wrong after a
            # rotation or a deploy, every row it touches — including target
            # database passwords — starts flowing as ciphertext where a plain
            # value was expected, with nothing pointing at the cause. It is
            # loud now instead.
            logger.error(
                "EncryptedText çözülemedi; ham değer döndürülüyor. "
                "QUERY_ENCRYPTION_KEY(S) yanlış olabilir veya bu satır hiç "
                "şifrelenmemiş (eski veri)."
            )
            return value

class User(Base):
    """
    User model.
    """
    __tablename__ = 'Users'
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String(50), unique=True, index=True)
    password = Column(String)
    email = Column(String(50), unique=True)
    is_active = Column(Boolean, nullable=False, default=True, server_default=sql_true(), index=True)
    is_platform_owner = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=sql_false(),
        index=True,
    )
    disabled_at = Column(AppDateTime, nullable=True)
    disabled_by = Column(String(50), nullable=True)
    created_at = Column(AppDateTime, nullable=False, default=db_now)
    last_login_at = Column(AppDateTime, nullable=True)

    def set_password(self, plain_password: str) -> None:
        """
        Hashes plain text password with bcrypt and stores it, enforcing B2B security policy.

        Synchronous, and at rounds=14 that is 1-2 seconds of CPU. Request
        handlers must call `aset_password` instead so the event loop keeps
        serving; this stays for tests, fixtures and the bootstrap CLI, where
        blocking costs nothing.

        Args:
            plain_password: The raw password string to hash.

        Raises:
            ValueError: If the password does not meet security policies.
        """
        validate_password_policy(plain_password)
        salt: bytes = bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
        self.password = bcrypt.hashpw(plain_password.encode('utf-8'), salt).decode('utf-8')

    async def aset_password(self, plain_password: str) -> None:
        """Hash and store a password without blocking the event loop.

        Args:
            plain_password: The raw password string to hash.

        Raises:
            ValueError: If the password does not meet security policies.
        """
        validate_password_policy(plain_password)
        self.password = await anyio.to_thread.run_sync(_hash_password, plain_password)

    def check_password(self, plain_password: str) -> bool:
        """
        Compares plain text password with hashed password.

        Synchronous; see `set_password`. Request handlers use `acheck_password`.

        Args:
            plain_password: The raw password string to check.

        Returns:
            bool: True if password matches, False otherwise.
        """
        return bcrypt.checkpw(plain_password.encode('utf-8'), self.password.encode('utf-8'))

    async def acheck_password(self, plain_password: str) -> bool:
        """Verify a password on a worker thread rather than the event loop.

        bcrypt at rounds=14 costs 1-2 seconds of CPU. Run inline from an async
        endpoint it stopped the entire worker for that time: every other
        request, query and audit write waited behind one login.
        """
        return await anyio.to_thread.run_sync(
            _verify_password, plain_password, self.password
        )

class ActionLogging(Base):
    """
    Query execution log model.
    """
    __tablename__ = 'ActionLogging'

    # --- Core fields ---
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey(User.id), index=True, nullable=False)
    username = Column(String(50), index=True, nullable=False)
    query_date = Column(AppDateTime, nullable=False)
    query = Column(EncryptedText, nullable=False)
    machine_name = Column(String(50), index=True, nullable=False)
    ExecutionDurationMS = Column(Integer, nullable=True)
    row_count = Column(Integer, nullable=True)
    isSuccessfull = Column(Boolean, nullable=True)
    ErrorMessage = Column(AppText, nullable=True)
    applied_masking_rules = Column(AppText, nullable=True)

    # --- Risk analysis ---
    risk_level = Column(String(50), nullable=True)

    # --- Approval ---
    approved_execution = Column(Boolean, nullable=True, default=False)  # kept for backward compatibility
    approval_status = Column(
        SAEnum(ApprovalStatus, name="approvalstatus"),
        nullable=False,
        default=ApprovalStatus.AUTO_APPROVED,
        index=True
    )
    approved_by = Column(String(100), nullable=True)          # WebQuery username or Slack email fallback
    approved_by_slack_id = Column(String(20), nullable=True)  # Immutable Slack user ID
    approved_at = Column(AppDateTime, nullable=True)

    # --- Context ---
    database_id = Column(Integer, ForeignKey("Databases.id"), nullable=True, index=True)
    trace_id = Column(String(36), nullable=True, index=True)  # UUID matching QueryData.uuid
    client_ip = Column(String(45), nullable=True)             # IPv6-safe length

class LoginLogging(Base):
    """
    User login/logout log model.
    """
    __tablename__ = "LoginLogging"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("Users.id"), nullable=False)
    login_date = Column(AppDateTime, nullable=False)
    client_ip = Column(String, nullable=False)
    logout_date = Column(AppDateTime, nullable=True)
    login_duration_ms = Column(Integer, nullable=True)

class QueryData(Base):
    """
    User query storage model.
    """
    __tablename__ = "QueryData"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("Users.id"), nullable=False)
    servername = Column(String(50))
    database_name = Column(String(50))
    query = Column(EncryptedText, nullable=False)
    uuid = Column(AppUUID, nullable=False, index=True)
    status = Column(String(50), nullable=False)
    risk_type = Column(String(50), nullable=True)
    decision_reason = Column(String(500), nullable=True)
    decided_by = Column(String(50), nullable=True)
    decided_at = Column(AppDateTime, nullable=True)
    
class Workspace(Base):
    """
    User workspace model.
    """
    __tablename__ = "Workspaces"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("Users.id"), nullable=False)
    # Free text the user types. String() maps to VARCHAR on MSSQL, and the
    # server codepage has no room for the Turkish-specific letters: a name
    # saved as "Veritabanı envanteri" reads back as "Veritabani envanteri".
    # User-entered text therefore has to be NVARCHAR. See SPEC-0012 BR-05.
    name = Column(AppNVarChar, nullable=False)
    description = Column(AppNVarChar, nullable=True)
    query_id = Column(Integer, ForeignKey("QueryData.id"), nullable=False, unique=True)
    show_results = Column(Boolean, nullable=True, default=None)
    query_data = relationship("QueryData")

class Databases(Base):
    """
    Registered target databases model.
    Stores connection details (server, database name, technology, credentials)
    for each database that users can query through WebQuery.
    """
    __tablename__ = "Databases"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    servername = Column(String(100), nullable=False)
    database_name = Column(String(100), nullable=False)
    technology = Column(String(100), nullable=False)
    # Target-database credentials, stored encrypted in WebQuery's metadata DB.
    # A database can be configured as ro, ro+rw, or ro+rw+ddl; absent tiers
    # are intentionally unavailable and must fail closed at execution time.
    username_ro = Column(String(100), nullable=True)
    password_ro = Column(EncryptedText, nullable=True)
    username_rw = Column(String(100), nullable=True)
    password_rw = Column(EncryptedText, nullable=True)
    username_ddl = Column(String(100), nullable=True)
    password_ddl = Column(EncryptedText, nullable=True)
    # Legacy generated credentials are kept only while existing deployments
    # transition to per-tier credentials. New registrations never populate them.
    db_username = Column(String(100), nullable=True)
    db_password = Column(EncryptedText, nullable=True)
    uuid = Column(AppUUID, nullable=False, index=True, default=lambda: str(uuid.uuid4()))
    # Retirement is a soft delete (OQ-2026-016). `ActionLogging.database_id`,
    # `MaskingRule` and `UserDatabaseAssociation` all reference this row, and
    # `QueryData` matches it by (servername, database_name); a hard delete would
    # orphan the audit trail it exists to preserve. Inactive registrations are
    # excluded from the catalogue and from every listing, so nothing can be
    # queried through them.
    is_active = Column(
        Boolean, nullable=False, default=True, server_default=sql_true(), index=True
    )
    retired_at = Column(AppDateTime, nullable=True)
    retired_by = Column(String(50), nullable=True)

    __table_args__ = (
        UniqueConstraint("servername", "database_name", name="uq_server_database"),
    )

class UserDatabaseAssociation(Base):
    """
    User-to-database access association model.
    Defines which users can access which databases and with what role
    (READER, WRITER, or ADMIN).

    ``role`` is the authoritative value: every authorization decision in the
    application reads it through ``common.roles``. ``is_admin`` is a mirror kept
    for API responses and existing queries, and is derived from ``role`` on the
    way to the database (see ``_derive_is_admin`` below) so the two cannot drift
    apart unnoticed.
    """
    __tablename__ = "UserDatabaseAssociation"
    user_id = Column(Integer, ForeignKey("Users.id"), primary_key=True, nullable=False)
    database_id = Column(Integer, ForeignKey("Databases.id"), primary_key=True, nullable=False)
    role = Column(String(50), nullable=False, default="READER") # "READER", "WRITER", "ADMIN"
    is_admin = Column(Boolean, nullable=False, default=False)


@event.listens_for(UserDatabaseAssociation, "before_insert")
@event.listens_for(UserDatabaseAssociation, "before_update")
def _derive_is_admin(mapper, connection, target: UserDatabaseAssociation) -> None:
    """Recompute the ``is_admin`` mirror from the authoritative ``role``.

    Done here rather than at each call site because there are five of them
    across ``admin/services.py`` and ``owner/services.py``, and a sixth that
    forgets to update the mirror would produce a row whose flag contradicts its
    role with nothing failing.
    """
    target.is_admin = ADMIN in parse_roles(target.role)


class MaskingRule(Base):
    """
    Table and column level masking rules defined by admin.
    """
    __tablename__ = "MaskingRules"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    database_id = Column(Integer, ForeignKey("Databases.id"), nullable=False)
    table_name = Column(String(100), nullable=False)
    column_name = Column(String(100), nullable=False)
    # Validated at the API boundary (`MaskingRuleSchema`), where the only
    # accepted value is "full". Left nullable so historical rows written before
    # that validation do not need a backfill; enforcement ignores the stored
    # value either way.
    masking_type = Column(String(50), default="full")
    is_active = Column(Boolean, default=True)

    # A column may be ruled once per table. The save path already rejects
    # duplicates inside one request body; this stops two concurrent saves — or a
    # direct write — from leaving two rows for the same column.
    __table_args__ = (
        UniqueConstraint(
            "database_id",
            "table_name",
            "column_name",
            name="uq_MaskingRules_database_table_column",
        ),
    )

# `BlacklistedToken` was removed (OQ-2026-014). `mint_access` never issued a
# `jti`, so the table was never written and its check never fired; ADR-0008's
# server-side `UserSession` rows carry revocation instead.


class UserSession(Base):
    """Server-side session state for refresh-token rotation and revocation."""
    __tablename__ = "UserSessions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("Users.id"), nullable=False, index=True)
    refresh_hash = Column(String(64), nullable=False, unique=True, index=True)
    prev_refresh_hash = Column(String(64), nullable=True, index=True)
    last_refresh_at = Column(AppDateTime, nullable=True)
    created_at = Column(AppDateTime, nullable=False)
    expires_at = Column(AppDateTime, nullable=False, index=True)
    revoked_at = Column(AppDateTime, nullable=True, index=True)
    revoked_reason = Column(String(200), nullable=True)
    client_ip = Column(String(45), nullable=True)
    user_agent = Column(String(300), nullable=True)


class AuditLog(Base):
    """Append-only audit record for non-query-execution security events.

    "Append-only" is enforced by this application, not by the database. The ORM
    guard below refuses an update or a delete, and no service writes one; but a
    session opened with the application's own database credentials can still
    change these rows. Closing that gap needs a database-side control the
    application cannot grant itself - a restricted writer principal with INSERT
    but not UPDATE/DELETE on this table, or an INSTEAD OF trigger - which is a
    deployment-time decision for the metadata DBA. See ADR-0009.
    """

    __tablename__ = "AuditLog"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    created_at = Column(AppDateTime, nullable=False, default=db_now, index=True)

    actor_user_id = Column(Integer, ForeignKey("Users.id"), nullable=True, index=True)
    actor_username = Column(String(50), nullable=True)
    actor_slack_id = Column(String(20), nullable=True)

    action = Column(String(64), nullable=False, index=True)
    target_type = Column(String(32), nullable=True)
    target_id = Column(String(64), nullable=True, index=True)
    details = Column(AppText, nullable=True)

    client_ip = Column(String(45), nullable=True)
    trace_id = Column(String(36), nullable=True, index=True)


class AuditLogImmutableError(RuntimeError):
    """Raised when application code tries to modify a written audit record."""


@event.listens_for(AuditLog, "before_update")
def _reject_audit_update(mapper, connection, target: AuditLog) -> None:
    raise AuditLogImmutableError(
        "AuditLog kayıtları değiştirilemez; düzeltme için yeni kayıt yazın."
    )


@event.listens_for(AuditLog, "before_delete")
def _reject_audit_delete(mapper, connection, target: AuditLog) -> None:
    raise AuditLogImmutableError("AuditLog kayıtları silinemez.")
