"""
Database Provider Configuration
List of accessible SQL Server instances and connection string templates.
"""
import logging
import os

from dotenv import load_dotenv
from sqlalchemy import event
from sqlalchemy.engine import URL

logger = logging.getLogger(__name__)

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


# Login (connect) timeout for SQL Server. This is deliberately not
# QUERY_TIMEOUT_SECONDS: pyodbc's ``connect(timeout=...)`` maps to
# SQL_ATTR_LOGIN_TIMEOUT, so reusing the query budget here would make an
# unreachable server hang for the full query timeout before failing. It matches
# the ``connection timeout`` value carried in the URL.
MSSQL_LOGIN_TIMEOUT_SECONDS = 30


def get_connect_args(tech: str, timeout_seconds: int) -> dict:
    """Return driver-specific timeout arguments for a target database."""
    tech = tech.lower().strip()

    if tech == "mssql":
        # pyodbc's connect(timeout=...) is SQL_ATTR_LOGIN_TIMEOUT, not the
        # statement execution timeout. The query budget is applied per
        # connection by ``apply_statement_timeout`` below.
        return {"timeout": MSSQL_LOGIN_TIMEOUT_SECONDS}

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
# Note: MySQL applies max_execution_time to read-only SELECT statements only, so
# DML on the ``rw`` tier is not covered by it.
SESSION_INIT_SQL = {
    "mysql": "SET SESSION max_execution_time = {ms}",
}


def apply_statement_timeout(engine, tech: str, timeout_seconds: int) -> None:
    """Attach a per-connection statement timeout for technologies that need one.

    PostgreSQL gets ``statement_timeout`` and MySQL gets ``max_execution_time``
    from :func:`get_connect_args` / :data:`SESSION_INIT_SQL`. SQL Server has no
    equivalent connect argument: pyodbc exposes the query budget as the mutable
    ``Connection.timeout`` attribute, which has to be set on each pooled
    connection as it is created.

    The aioodbc adapter declares ``__slots__``, so the attribute is set on the
    raw pyodbc connection underneath it — the same route SQLAlchemy's own
    ``autocommit`` setter takes for this driver.
    """
    if tech.lower().strip() != "mssql" or timeout_seconds <= 0:
        return

    sync_engine = getattr(engine, "sync_engine", engine)

    @event.listens_for(sync_engine, "connect")
    def _set_pyodbc_query_timeout(dbapi_connection, _connection_record):
        raw = getattr(dbapi_connection, "_connection", dbapi_connection)
        raw = getattr(raw, "_conn", raw)
        try:
            raw.timeout = timeout_seconds
        except (AttributeError, TypeError):
            # A driver that does not expose a mutable timeout must not take the
            # connection down; the absence is visible in the log instead.
            logger.warning(
                "Hedef bağlantıda ifade zaman aşımı ayarlanamadı (tech=%s)", tech
            )

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


# ODBC query parameters shared by every SQL Server URL we build.
_MSSQL_QUERY = {
    "driver": "ODBC Driver 18 for SQL Server",
    "TrustServerCertificate": "yes",
    "connection timeout": "30",
}


def _split_host_port(servername: str) -> tuple[str, int | None]:
    """Split ``host:port`` without breaking bare hosts or IPv6 literals.

    ``URL.create`` takes host and port separately. A named SQL Server instance
    (``host\\INSTANCE``) has no port and must pass through untouched.
    """
    host = servername.strip()
    if host.startswith("["):  # IPv6 literal, optionally [::1]:1433
        closing = host.find("]")
        if closing != -1:
            remainder = host[closing + 1 :]
            if remainder.startswith(":") and remainder[1:].isdigit():
                return host[1:closing], int(remainder[1:])
            return host[1:closing], None
        return host, None
    if host.count(":") == 1:
        candidate_host, _, candidate_port = host.partition(":")
        if candidate_port.isdigit():
            return candidate_host, int(candidate_port)
    return host, None


# Connection string builder functions
def create_connection_string(tech: str, driver: str, username: str, password: str, servername: str, database: str) -> str:
    """
    Generates a database connection string using centralized or custom credentials.
    Formats the string dynamically based on the technology.

    The URL is assembled with ``sqlalchemy.engine.URL.create`` rather than an
    f-string. Target credentials are created by the target DBA (OQ-2026-002), so
    their character set is outside WebQuery's control: a password containing
    ``@``, ``/``, ``:``, ``?`` or ``#`` interpolated directly would re-parse into
    a different host, database and password. ``URL.create`` percent-encodes each
    component, and ``make_url`` round-trips it back to the original values.

    Args:
        tech: Database technology e.g., mssql, mysql, postgresql.
        driver: Database driver e.g., aioodbc, aiomysql, asyncpg.
        username: Database username.
        password: Database password.
        servername: Database server hostname or IP.
        database: Target database name.

    Returns:
        str: Formatted connection string with every component escaped.
    """
    tech = tech.lower().strip()
    host, port = _split_host_port(servername)

    if tech == "mysql":
        drivername = f"mysql+{driver}"
        query: dict[str, str] = {}
    elif tech in ("postgresql", "postgres"):
        drivername = f"postgresql+{driver}"
        query = {}
    elif tech == "mssql":
        drivername = f"mssql+{driver}"
        query = dict(_MSSQL_QUERY)
    else:
        # Unknown technologies keep the historical SQL Server shape.
        drivername = f"{tech}+{driver}"
        query = dict(_MSSQL_QUERY)

    url = URL.create(
        drivername,
        username=username,
        password=password,
        host=host,
        port=port,
        database=database,
        query=query,
    )
    return url.render_as_string(hide_password=False)


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
    return create_connection_string(
        tech="mssql",
        driver="aioodbc",
        username=DB_USER,
        password=DB_PASSWORD,
        servername=server,
        database="master",
    )
