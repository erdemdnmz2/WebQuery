"""
Application Database Models
SQLAlchemy ORM models for the application database
"""
import base64
import os
import re
import bcrypt
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean, Text
from sqlalchemy.dialects.mssql import DATETIME2, VARCHAR, NVARCHAR, UNIQUEIDENTIFIER, TEXT as MSSQL_TEXT
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.types import TypeDecorator
from cryptography.fernet import Fernet

Base = declarative_base()

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
    is_admin = Column(Boolean)

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
    approved_execution = Column(Boolean, nullable=True, default=False)
    applied_masking_rules = Column(AppText, nullable=True)

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
    name = Column(String(100), nullable=False)
    description = Column(String(255), nullable=True)
    query_id = Column(Integer, ForeignKey("QueryData.id"), nullable=False, unique=True)
    show_results = Column(Boolean, nullable=True, default=None)
    query_data = relationship("QueryData")

class Databases(Base):
    __tablename__ = "Databases"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    servername = Column(String(100), nullable=False)
    database_name = Column(String(100), nullable=False)
    technology = Column(String(100), nullable=False)
    db_username = Column(String(100), nullable=True)
    db_password = Column(EncryptedText, nullable=True)

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