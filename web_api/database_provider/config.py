"""
Database Provider Configuration
List of accessible SQL Server instances and connection string templates.
"""
import os

from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Retrieve comma-separated server list from environment, otherwise use default
_server_list = os.getenv("SQL_SERVER_NAMES", "localhost")
SERVER_NAMES: list[str] = [s.strip() for s in _server_list.split(",") if s.strip()]

# SQL Server authentication credentials.
# There is intentionally no privileged default: a missing value must remain
# visible to startup validation instead of silently becoming "sa".
DB_USER = os.getenv("DB_USER", "")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

# Central service account credentials for executing queries on target databases
CENTRAL_DB_USER: str = os.getenv("CENTRAL_DB_USER") or DB_USER
CENTRAL_DB_PASSWORD: str = os.getenv("CENTRAL_DB_PASSWORD") or DB_PASSWORD

# Engine Cache Cleanup Interval (seconds)
# Default: 1800 seconds (30 minutes)
TIME_INTERVAL_FOR_CACHE = int(os.getenv("ENGINE_CACHE_TTL_SECONDS", "1800"))

# Maximum execution time for a target database query, in seconds.
# This is distinct from connection and connection-pool acquisition timeouts.
QUERY_TIMEOUT_SECONDS = int(os.getenv("QUERY_TIMEOUT_SECONDS", "300"))

# Technology to Driver mapping
TECHNOLOGY_DRIVER_MAP = {
    "mssql": "aioodbc",
    "mysql": "aiomysql",
    "postgresql": "asyncpg",
    "postgres": "asyncpg",  
}


def get_connect_args(tech: str, timeout_seconds: int) -> dict:
    """Return driver-specific timeout arguments for a target database."""
    tech = tech.lower().strip()

    if tech == "mssql":
        # aioodbc/pyodbc applies this as the statement execution timeout.
        return {"timeout": timeout_seconds}

    if tech in ("postgresql", "postgres"):
        timeout_ms = timeout_seconds * 1000
        return {
            "command_timeout": timeout_seconds,
            "server_settings": {
                "statement_timeout": str(timeout_ms),
                "idle_in_transaction_session_timeout": str(
                    (timeout_seconds + 30) * 1000
                ),
            },
        }

    if tech == "mysql":
        # max_execution_time is applied after connection creation below.
        return {"connect_timeout": 15}

    return {}


# MySQL's query execution limit is a session setting rather than a connect arg.
SESSION_INIT_SQL = {
    "mysql": "SET SESSION max_execution_time = {ms}",
}

def get_driver_for_technology(technology: str) -> str:
    """
    Returns the appropriate driver for a given database technology.
    
    Args:
        technology: Database technology (e.g., mssql, mysql, postgresql, etc.).
        
    Returns:
        str: Corresponding driver name (e.g., aioodbc, aiomysql, asyncpg).
        
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


# Connection string builder functions
def create_connection_string(tech: str, driver: str, username: str, password: str, servername: str, database: str) -> str:
    """
    Generates a database connection string using centralized or custom credentials.
    Formats the string dynamically based on the technology.
    
    Args:
        tech: Database technology e.g., mssql, mysql, postgresql.
        driver: Database driver e.g., aioodbc, aiomysql, asyncpg.
        username: Database username.
        password: Database password.
        servername: Database server hostname or IP.
        database: Target database name.
        
    Returns:
        str: Formatted connection string.
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
        # Fallback to MSSQL format
        return (
            f"{tech}+{driver}://{username}:{password}@{servername}/{database}"
            "?driver=ODBC+Driver+18+for+SQL+Server"
            "&TrustServerCertificate=yes"
            "&connection timeout=30"
        )


def get_master_connection_string(server: str) -> str:
    """
    Generates a connection string for connecting to the master database.
    Used for administrative metadata retrieval (e.g., sys.databases query).
    
    Args:
        server: SQL Server instance name or address.
        
    Returns:
        str: Connection string for the master database.
        
    Note:
        DB_USER and DB_PASSWORD are fetched from the environment variables.
    """
    return (
        f"mssql+aioodbc://{DB_USER}:{DB_PASSWORD}@{server}/master"
        "?driver=ODBC+Driver+18+for+SQL+Server"
        "&TrustServerCertificate=yes"
        "&connection timeout=30"
    )
