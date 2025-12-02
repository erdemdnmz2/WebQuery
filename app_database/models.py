"""
Application Database Models
Uygulama veritabanı için SQLAlchemy ORM modelleri
"""
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean
from sqlalchemy.dialects.mssql import DATETIME2, VARCHAR, NVARCHAR, UNIQUEIDENTIFIER, TEXT
from sqlalchemy.orm import relationship, declarative_base
from passlib.context import CryptContext

Base = declarative_base()

pwd_context = CryptContext(schemes=["bcrypt"])

class User(Base):
    """
    Kullanıcı modeli
    
    Attributes:
        id: Primary key
        username: Kullanıcı adı (unique)
        password: Bcrypt hash'lenmiş şifre
        email: Email adresi (unique)
        is_admin: Admin yetkisi (admin query risk kontrolünden muaf)
    """
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String(50), unique=True, index=True)
    password = Column(String)
    email = Column(String(50), unique=True)
    is_admin = Column(Boolean)

    def set_password(self, plain_password):
        """Düz metin şifreyi bcrypt ile hash'leyerek saklar"""
        self.password = pwd_context.hash(plain_password)
    
    def check_password(self, plain_password):
        """Düz metin şifreyi hash'lenmiş şifre ile karşılaştırır"""
        return pwd_context.verify(plain_password, self.password)

class ActionLogging(Base):
    """
    Query execution log modeli
    
    Her query çalıştırma işlemi için log kaydı tutar.
    Başarı/başarısızlık, süre, satır sayısı gibi metrikleri saklar.
    
    Attributes:
        id: Primary key
        user_id: Kullanıcı foreign key
        username: Kullanıcı adı (denormalized for reporting)
        query_date: Query başlangıç zamanı
        query: Çalıştırılan SQL query
        machine_name: SQL Server instance adı
        ExecutionDurationMS: Çalışma süresi (milisaniye)
        row_count: Dönen satır sayısı
        isSuccessfull: Başarı durumu
        ErrorMessage: Hata mesajı (varsa)
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
    # Flag to indicate the execution was performed after admin approval
    approved_execution = Column(Boolean, nullable=True, default=False)

class LoginLogging(Base):
    """
    Kullanıcı login/logout log modeli
    
    Her login/logout işlemi için kayıt tutar.
    Session süresini ve IP adresini loglar.
    
    Attributes:
        id: Primary key
        user_id: Kullanıcı foreign key
        login_date: Giriş zamanı
        client_ip: İstek yapan IP adresi
        logout_date: Çıkış zamanı (NULL ise hala aktif)
        login_duration_ms: Session süresi (milisaniye)
    """
    __tablename__ = "LoginLogging"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    login_date = Column(DATETIME2(precision=7), nullable=False)
    client_ip = Column(String, nullable=False)
    logout_date = Column(DATETIME2(precision=7), nullable=True)
    login_duration_ms = Column(Integer, nullable=True)

class QueryData(Base):
    """
    Kullanıcı query saklama modeli (workspace için)
    
    Kullanıcıların kaydettiği query'leri ve metadata'larını tutar.
    
    Attributes:
        id: Primary key
        user_id: Kullanıcı foreign key
        servername: Hedef SQL Server
        database_name: Hedef veritabanı
        query: Kaydedilen SQL query
        uuid: Unique identifier
        status: Query durumu
        risk_type: Risk analizi sonucu (varsa)
    """
    __tablename__ = "QueryData"
    id = Column(Integer, primary_key=True, index=True,autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    servername = Column(VARCHAR(50))
    database_name = Column(VARCHAR(50))
    query = Column(TEXT, nullable=False)
    uuid = Column(UNIQUEIDENTIFIER, nullable=False, index=True)
    status = Column(VARCHAR(50), nullable=False)
    risk_type = Column(NVARCHAR(50), nullable=True)
    cached_results = Column(TEXT, nullable = True)
    cache_timestamp = Column(DATETIME2(precision=7), nullable=True)

class Workspace(Base):
    """
    Kullanıcı workspace modeli
    
    Kullanıcıların query'lerini gruplandırması ve düzenlemesi için.
    
    Attributes:
        id: Primary key
        user_id: Kullanıcı foreign key
        name: Workspace adı
        description: Workspace açıklaması
        query_id: İlişkili query foreign key (unique - 1:1 relationship)
        query_data: queryData ile relationship
    """
    __tablename__ = "Workspaces"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(NVARCHAR(100), nullable=False)
    description = Column(NVARCHAR(255), nullable=True)
    query_id = Column(Integer, ForeignKey("queryData.id"), nullable=False, unique=True)
    show_results = Column(Boolean, nullable=True, default=None)
    query_data = relationship("QueryData")

class Databases(Base):
    __tablename__ = "Databases"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    servername = Column(NVARCHAR(100), nullable=False)
    database_name = Column(NVARCHAR(100), nullable=False)
    technology = Column(NVARCHAR(100), nullable=False)