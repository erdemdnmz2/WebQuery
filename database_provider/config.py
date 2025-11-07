"""
Database Provider Configuration
Erişilebilir SQL Server instance listesi ve connection string template
"""
import os
from typing import List
from dotenv import load_dotenv

# .env dosyasını yükle
load_dotenv()

# Environment'tan virgülle ayrılmış server listesi al, yoksa default kullan
_server_list = os.getenv("SQL_SERVER_NAMES", "localhost")
SERVER_NAMES: List[str] = [s.strip() for s in _server_list.split(",") if s.strip()]

# SQL Server authentication credentials
DB_USER = os.getenv("DB_USER", "sa")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

TIME_INTERVAL_FOR_CACHE = 1800 # in seconds

# Connection string builder fonksiyonları
def create_connection_string(tech : str, driver: str, username: str, password: str, servername: str, database: str) -> str:
    """
    Kullanıcıya özel SQL Server connection string oluşturur.
    
    Args:
        tech: Kullanılacak teknoloji örn: MSSQL, MYSQL, PostgreSQl
        username: SQL Server kullanıcı adı
        password: SQL Server şifresi
        servername: SQL Server instance adı (ör: localhost, server1)
        database: Bağlanılacak veritabanı adı
        
    Returns:
        str: İstenilen connection string
    """
    return (
        f"{tech}+{driver}://{username}:{password}@{servername}/{database}"
        "?driver=ODBC+Driver+18+for+SQL+Server"
        "&TrustServerCertificate=yes"
        "&connection timeout=30"
    )

def get_master_connection_string(server: str) -> str:
    """
    Master database'e bağlanmak için connection string oluşturur.
    Veritabanı listesini almak için kullanılır (sys.databases sorgusu).
    
    Args:
        server: SQL Server instance adı
        
    Returns:
        str: Master database için connection string
        
    Note:
        DB_USER ve DB_PASSWORD environment variable'larından alınır
    """
    return (
        f"mssql+aioodbc://{DB_USER}:{DB_PASSWORD}@{server}/master"
        "?driver=ODBC+Driver+18+for+SQL+Server"
        "&TrustServerCertificate=yes"
        "&connection timeout=30"
    )
