"""
Application Database Models
SQLAlchemy ORM models for the application database
"""
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean
from sqlalchemy.dialects.mssql import DATETIME2, VARCHAR, NVARCHAR, UNIQUEIDENTIFIER, TEXT
from sqlalchemy.orm import relationship, declarative_base
import bcrypt

Base = declarative_base()

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
    username = Column(VARCHAR(50), index=True, nullable=False)
    query_date = Column(DATETIME2(precision=7), nullable=False)
    query = Column(TEXT, nullable=False)
    machine_name = Column(VARCHAR(50), index=True, nullable=False)
    ExecutionDurationMS = Column(Integer, nullable=True)
    row_count = Column(Integer, nullable=True)
    isSuccessfull = Column(Boolean, nullable=True)
    ErrorMessage = Column(TEXT, nullable=True)
    approved_execution = Column(Boolean, nullable=True, default=False)

class LoginLogging(Base):
    """
    User login/logout log model.
    """
    __tablename__ = "LoginLogging"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("Users.id"), nullable=False)
    login_date = Column(DATETIME2(precision=7), nullable=False)
    client_ip = Column(String, nullable=False)
    logout_date = Column(DATETIME2(precision=7), nullable=True)

class QueryData(Base):
    """
    User query storage model.
    """
    __tablename__ = "QueryData"
    id = Column(Integer, primary_key=True, index=True,autoincrement=True)
    user_id = Column(Integer, ForeignKey("Users.id"), nullable=False)
    servername = Column(VARCHAR(50))
    database_name = Column(VARCHAR(50))
    query = Column(TEXT, nullable=False)
    uuid = Column(UNIQUEIDENTIFIER, nullable=False, index=True)
    status = Column(VARCHAR(50), nullable=False)
    risk_type = Column(NVARCHAR(50), nullable=True)
    
class Workspace(Base):
    """
    User workspace model.
    """
    __tablename__ = "Workspaces"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("Users.id"), nullable=False)
    name = Column(NVARCHAR(100), nullable=False)
    description = Column(NVARCHAR(255), nullable=True)
    query_id = Column(Integer, ForeignKey("QueryData.id"), nullable=False, unique=True)
    show_results = Column(Boolean, nullable=True, default=None)
    query_data = relationship("QueryData")

class Databases(Base):
    __tablename__ = "Databases"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    servername = Column(NVARCHAR(100), nullable=False)
    database_name = Column(NVARCHAR(100), nullable=False)
    technology = Column(NVARCHAR(100), nullable=False)