"""
Application Database Models
SQLAlchemy ORM models for the application database
"""
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean, Text
from sqlalchemy.dialects.mssql import DATETIME2, VARCHAR, NVARCHAR, UNIQUEIDENTIFIER, TEXT as MSSQL_TEXT
from sqlalchemy.orm import relationship, declarative_base
import bcrypt

Base = declarative_base()

# Define cross-db compatible types
AppDateTime = DateTime().with_variant(DATETIME2(precision=7), "mssql")
AppVarChar = String().with_variant(VARCHAR(length=None), "mssql")
AppNVarChar = String().with_variant(NVARCHAR(length=None), "mssql")
AppText = Text().with_variant(MSSQL_TEXT(), "mssql")
AppUUID = String(36).with_variant(UNIQUEIDENTIFIER(), "mssql")

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

    def set_password(self, plain_password):
        """Hashes plain text password with bcrypt and stores it"""
        salt = bcrypt.gensalt()
        self.password = bcrypt.hashpw(plain_password.encode('utf-8'), salt).decode('utf-8')
    
    def check_password(self, plain_password):
        """Compares plain text password with hashed password"""
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
    query = Column(AppText, nullable=False)
    machine_name = Column(String(50), index=True, nullable=False)
    ExecutionDurationMS = Column(Integer, nullable=True)
    row_count = Column(Integer, nullable=True)
    isSuccessfull = Column(Boolean, nullable=True)
    ErrorMessage = Column(AppText, nullable=True)
    approved_execution = Column(Boolean, nullable=True, default=False)

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

class QueryData(Base):
    """
    User query storage model.
    """
    __tablename__ = "QueryData"
    id = Column(Integer, primary_key=True, index=True,autoincrement=True)
    user_id = Column(Integer, ForeignKey("Users.id"), nullable=False)
    servername = Column(String(50))
    database_name = Column(String(50))
    query = Column(AppText, nullable=False)
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