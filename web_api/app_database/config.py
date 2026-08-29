"""
Application Database Configuration

Application metadata database connection settings.
Used for user management, auditing logs, and workspace configuration storage.

Environment Variables:
    DB_USER: SQL Server username (required when APP_DATABASE_URL is not set)
    DB_PASSWORD: SQL Server password (required when APP_DATABASE_URL is not set)
    APP_DATABASE_URL: Full connection string (optional override)
"""
import os

from dotenv import load_dotenv

from database_provider.config import create_connection_string

load_dotenv(".env.production")
load_dotenv()

# Do not silently fall back to the highly privileged SQL Server `sa` account.
# Startup validation requires APP_DATABASE_URL in deployed environments; these
# values are only used when that explicit URL is absent.
db_user = os.getenv("DB_USER", "")
db_password = os.getenv("DB_PASSWORD", "")
db_host = os.getenv("DB_HOST", "localhost")
db_name = os.getenv("DB_NAME", "dba_application_db")

# Built through the shared escaping URL builder rather than an f-string: a
# DB_PASSWORD containing '@', '/', ':', '?' or '#' would otherwise re-parse into
# a different host and password. See docs/adr/ADR-0019.
DATABASE_URL = os.getenv("APP_DATABASE_URL") or create_connection_string(
    tech="mssql",
    driver="aioodbc",
    username=db_user,
    password=db_password,
    servername=db_host,
    database=db_name,
)
