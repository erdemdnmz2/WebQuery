from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean
from sqlalchemy.dialects.mssql import DATETIME2, VARCHAR, NVARCHAR, UNIQUEIDENTIFIER, TEXT
from sqlalchemy.orm import relationship, declarative_base
from passlib.context import CryptContext

Base = declarative_base()

pwd_context = CryptContext(schemes=["bcrypt"])

#user_schema = UserSchema.model_validate(user) ile user modeli ile user modelini schema ya çeviriyoruz

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String(50), unique=True, index=True)
    password = Column(String)
    email = Column(String(50), unique=True)
    is_admin = Column(Boolean)

    def set_password(self, plain_password):
        self.password = pwd_context.hash(plain_password)
    
    def check_password(self, plain_password):
        return pwd_context.verify(plain_password, self.password)

class actionLogging(Base):
    __tablename__ = 'actionLogging'
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

class loginLogging(Base):
    __tablename__= "loginLogging"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    login_date = Column(DATETIME2(precision=7), nullable=False)
    client_ip = Column(String, nullable=False)
    logout_date = Column(DATETIME2(precision=7), nullable=True)

class queryData(Base):
    __tablename__ = "queryData"
    id = Column(Integer, primary_key=True, index=True,autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    servername = Column(VARCHAR(50))
    database_name = Column(VARCHAR(50))
    query = Column(TEXT, nullable=False)
    uuid = Column(UNIQUEIDENTIFIER, nullable=False, index=True)
    status = Column(VARCHAR(50), nullable=False)
    risk_type = Column(NVARCHAR(50), nullable=True)

class Workspace(Base):
    __tablename__ = "workspaces"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(NVARCHAR(100), nullable=False)
    description = Column(NVARCHAR(255), nullable=True)
    query_id = Column(Integer, ForeignKey("queryData.id"), nullable=False, unique=True)
    query_data = relationship("queryData")

# class accessibleTables(Base): burada kullanılabilir databaseleri görüntüleyip kaydedebiliriz ilk seferde böylece uygulama her açıldığında kullanıcının erişebildiği veritabanlarını görüntüleyebiliriz.
