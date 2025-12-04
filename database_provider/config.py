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

# Engine Cache Cleanup Interval (seconds)
# Default: 1800 seconds (30 minutes)
TIME_INTERVAL_FOR_CACHE = int(os.getenv("ENGINE_CACHE_TTL_SECONDS", "1800"))

# Technology to Driver mapping
TECHNOLOGY_DRIVER_MAP = {
    "mssql": "aioodbc",
    "mysql": "aiomysql",
    "postgresql": "asyncpg",
    "postgres": "asyncpg",  
}

def get_driver_for_technology(technology: str) -> str:
    """
    Database technology'sine göre uygun driver'ı döndürür.
    
    Args:
        technology: Database teknolojisi (mssql, mysql, postgresql, vb.)
        
    Returns:
        str: İlgili driver adı (aioodbc, aiomysql, asyncpg)
        
    Example:
        >>> get_driver_for_technology("mssql")
        'aioodbc'
        >>> get_driver_for_technology("mysql")
        'aiomysql'
        >>> get_driver_for_technology("postgresql")
        'asyncpg'
    """
    tech = technology.lower().strip()
    return TECHNOLOGY_DRIVER_MAP.get(tech, "aioodbc")  # default: aioodbc

# Connection string builder fonksiyonları
def create_connection_string(tech: str, driver: str, username: str, password: str, servername: str, database: str) -> str:
    """
    Kullanıcıya özel database connection string oluşturur.
    Technology'ye göre uygun format kullanır.
    
    Args:
        tech: Kullanılacak teknoloji örn: mssql, mysql, postgresql
        driver: Kullanılacak driver örn: aioodbc, aiomysql, asyncpg
        username: Database kullanıcı adı
        password: Database şifresi
        servername: Database server adı (ör: localhost, server1)
        database: Bağlanılacak veritabanı adı
        
    Returns:
        str: İstenilen connection string
    """
    tech = tech.lower()
    
    if tech == "mssql":
        # Microsoft SQL Server
        return (
            f"mssql+{driver}://{username}:{password}@{servername}/{database}"
            "?driver=ODBC+Driver+18+for+SQL+Server"
            "&TrustServerCertificate=yes"
            "&connection timeout=30"
        )
    elif tech == "mysql":
        # MySQL
        return f"mysql+{driver}://{username}:{password}@{servername}/{database}"
    elif tech == "postgresql" or tech == "postgres":
        # PostgreSQL
        return f"postgresql+{driver}://{username}:{password}@{servername}/{database}"
    else:
        # Default olarak MSSQL formatını kullan
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
