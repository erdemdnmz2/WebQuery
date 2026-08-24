"""
Application Database Models
SQLAlchemy ORM models for the application database
"""
from sqlalchemy import null
from sqlalchemy import UniqueConstraint
import base64
import os
import re
import bcrypt
import enum
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean, Text, Enum as SAEnum
from sqlalchemy.dialects.mssql import DATETIME2, VARCHAR, NVARCHAR, UNIQUEIDENTIFIER, TEXT as MSSQL_TEXT
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.types import TypeDecorator
from cryptography.fernet import Fernet

import uuid

Base = declarative_base()


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
    Uses QUERY_ENCRYPTION_KEY environment variable.
    """
    impl = Text
    
    _fernet = None

    @classmethod
    def _get_fernet(cls):
        if cls._fernet is None:
            key = os.getenv("QUERY_ENCRYPTION_KEY")
            if not key:
                # Generate a consistent fallback key for testing/development
                key = base64.urlsafe_b64encode(b"thirty-two-bytes-consistent-key!")
            cls._fernet = Fernet(key)
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
            # Fallback to returning raw value if decryption fails (e.g. for legacy plaintext data)
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

    def set_password(self, plain_password: str) -> None:
        """
        Hashes plain text password with bcrypt and stores it, enforcing B2B security policy.
        
        Args:
            plain_password: The raw password string to hash.
            
        Raises:
            ValueError: If the password does not meet security policies.
        """
        if len(plain_password) < 12:
            raise ValueError("Şifre en az 12 karakter olmalıdır.")
        if not re.search(r'[A-Z]', plain_password) or not re.search(r'[0-9]', plain_password):
            raise ValueError("Şifre en az bir büyük harf ve bir rakam içermelidir.")
            
        salt: bytes = bcrypt.gensalt(rounds=14)
        self.password = bcrypt.hashpw(plain_password.encode('utf-8'), salt).decode('utf-8')
    
    def check_password(self, plain_password: str) -> bool:
        """
        Compares plain text password with hashed password.
        
        Args:
            plain_password: The raw password string to check.
            
        Returns:
            bool: True if password matches, False otherwise.
        """
        return bcrypt.checkpw(plain_password.encode('utf-8'), self.password.encode('utf-8'))

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
    db_username = Column(String(100), nullable=True)
    db_password = Column(EncryptedText, nullable=True)
    uuid = Column(AppUUID, nullable=False, index=True, default=lambda: str(uuid.uuid4()))

    __table_args__ = (
        UniqueConstraint("servername", "database_name", name="uq_server_database"),
    )

class UserDatabaseAssociation(Base):
    """
    User-to-database access association model.
    Defines which users can access which databases and with what role
    (READER, WRITER, or ADMIN).
    """
    __tablename__ = "UserDatabaseAssociation"
    user_id = Column(Integer, ForeignKey("Users.id"), primary_key=True, nullable=False)
    database_id = Column(Integer, ForeignKey("Databases.id"), primary_key=True, nullable=False)
    role = Column(String(50), nullable=False, default="READER") # "READER", "WRITER", "ADMIN"
    is_admin = Column(Boolean, nullable=False, default=False)
    

class MaskingRule(Base):
    """
    Table and column level masking rules defined by admin.
    """
    __tablename__ = "MaskingRules"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    database_id = Column(Integer, ForeignKey("Databases.id"), nullable=False)
    table_name = Column(String(100), nullable=False)
    column_name = Column(String(100), nullable=False)
    masking_type = Column(String(50), default="default")
    is_active = Column(Boolean, default=True)

class BlacklistedToken(Base):
    """
    Blacklisted JTI tokens upon logout.
    """
    __tablename__ = "BlacklistedTokens"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    jti = Column(String(100), unique=True, index=True, nullable=False)
    expires_at = Column(AppDateTime, nullable=False)