"""
Application Database Configuration

Uygulama veritabanı bağlantı ayarları.
Kullanıcı yönetimi, loglama ve workspace verilerini tutan veritabanı için kullanılır.

Environment Variables:
    DB_USER: SQL Server kullanıcı adı (default: "sa")
    DB_PASSWORD: SQL Server şifresi (default: "")
    APP_DATABASE_URL: Tam connection string (override için)
"""
import os
from dotenv import load_dotenv

load_dotenv(".env.production")
load_dotenv()

db_user = os.getenv("DB_USER", "sa")
db_password = os.getenv("DB_PASSWORD", "")
db_host = os.getenv("DB_HOST", "localhost")
db_name = os.getenv("DB_NAME", "dba_application_db")

DATABASE_URL = os.getenv(
    "APP_DATABASE_URL",
    (
        f"mssql+aioodbc://{db_user}:{db_password}@{db_host}/{db_name}"
        "?driver=ODBC+Driver+18+for+SQL+Server"
        "&TrustServerCertificate=yes"
        "&connection timeout=30"
    )
)