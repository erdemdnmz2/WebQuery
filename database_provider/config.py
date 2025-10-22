"""
Database Provider Configuration
Erişilebilir SQL Server instance listesi ve connection string template
"""
import os
from typing import List

# Environment'tan virgülle ayrılmış server listesi al, yoksa default kullan
_server_list = os.getenv("SQL_SERVER_NAMES", "localhost")
SERVER_NAMES: List[str] = [s.strip() for s in _server_list.split(",") if s.strip()]

# SQL Server authentication credentials
DB_USER = os.getenv("DB_USER", "sa")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

# Connection string builder fonksiyonları
def create_connection_string(username: str, password: str, servername: str, database: str) -> str:
    """User-specific connection string oluşturur"""
    return (
        f"mssql+aioodbc://{username}:{password}@{servername}/{database}"
        "?driver=ODBC+Driver+18+for+SQL+Server"
        "&TrustServerCertificate=yes"
        "&connection timeout=30"
    )

def get_master_connection_string(server: str) -> str:
    """Master database connection string (database listesini almak için)"""
    return (
        f"mssql+aioodbc://{DB_USER}:{DB_PASSWORD}@{server}/master"
        "?driver=ODBC+Driver+18+for+SQL+Server"
        "&TrustServerCertificate=yes"
        "&connection timeout=30"
    )
