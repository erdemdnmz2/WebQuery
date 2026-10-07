import importlib


def test_database_provider_config_does_not_default_to_sa(monkeypatch):
    monkeypatch.setenv("DB_USER", "")
    monkeypatch.setenv("DB_PASSWORD", "")
    monkeypatch.setenv("CENTRAL_DB_USER", "")
    monkeypatch.setenv("CENTRAL_DB_PASSWORD", "")

    from database_provider import config

    config = importlib.reload(config)

    assert config.DB_USER == ""
    assert config.CENTRAL_DB_USER == ""


def test_app_database_config_does_not_default_to_sa(monkeypatch):
    monkeypatch.setenv("DB_USER", "")
    monkeypatch.setenv("DB_PASSWORD", "")
    monkeypatch.setenv("APP_DATABASE_URL", "")

    from app_database import config

    config = importlib.reload(config)

    assert config.db_user == ""


def test_target_query_timeout_defaults_to_five_minutes(monkeypatch):
    monkeypatch.delenv("QUERY_TIMEOUT_SECONDS", raising=False)

    from database_provider import config

    config = importlib.reload(config)

    assert config.QUERY_TIMEOUT_SECONDS == 300


def test_connect_args_for_mssql_carry_the_login_timeout_not_the_query_budget():
    """pyodbc's connect(timeout=) is SQL_ATTR_LOGIN_TIMEOUT, not a query timeout.

    Passing QUERY_TIMEOUT_SECONDS here made an unreachable server hang for the
    whole query budget before failing, and left the statement itself untimed.
    """
    from database_provider.config import MSSQL_LOGIN_TIMEOUT_SECONDS, get_connect_args

    assert get_connect_args("mssql", 120) == {"timeout": MSSQL_LOGIN_TIMEOUT_SECONDS}
    assert MSSQL_LOGIN_TIMEOUT_SECONDS < 120


def test_mssql_statement_timeout_is_set_on_the_raw_connection():
    """The query budget reaches SQL Server as pyodbc's mutable Connection.timeout."""
    from sqlalchemy import event

    from database_provider.config import apply_statement_timeout

    class RawConnection:
        timeout = 0

    class AioodbcConnection:
        """Mirrors AsyncAdapt_aioodbc_connection: __slots__, wraps _connection._conn."""

        __slots__ = ("_connection",)

        def __init__(self, raw):
            self._connection = type("Inner", (), {"_conn": raw})()

    class FakeEngine:
        pass

    raw = RawConnection()
    engine = FakeEngine()
    captured = {}

    def fake_listens_for(target, identifier):
        def decorator(fn):
            captured[identifier] = fn
            return fn

        return decorator

    original = event.listens_for
    event.listens_for = fake_listens_for
    try:
        apply_statement_timeout(engine, "mssql", 120)
    finally:
        event.listens_for = original

    assert "connect" in captured
    captured["connect"](AioodbcConnection(raw), None)
    assert raw.timeout == 120


def test_statement_timeout_is_a_no_op_for_non_mssql():
    from database_provider.config import apply_statement_timeout

    # Must not touch SQLAlchemy events at all for drivers that carry the
    # timeout in connect args or session SQL instead.
    apply_statement_timeout(object(), "postgresql", 120)
    apply_statement_timeout(object(), "mysql", 120)
    apply_statement_timeout(object(), "mssql", 0)


def test_connect_args_for_postgresql():
    from database_provider.config import get_connect_args

    assert get_connect_args("postgresql", 120) == {
        "command_timeout": 120,
        "server_settings": {
            "statement_timeout": "120000",
            "idle_in_transaction_session_timeout": "150000",
        },
    }


def test_mysql_uses_session_init_sql_for_query_timeout():
    from database_provider.config import SESSION_INIT_SQL, get_connect_args

    assert get_connect_args("mysql", 120) == {"connect_timeout": 15}
    assert SESSION_INIT_SQL["mysql"] == (
        "SET SESSION max_execution_time = {ms}"
    )


def test_unknown_database_has_no_driver_specific_connect_args():
    from database_provider.config import get_connect_args

    assert get_connect_args("unknown", 120) == {}


# --- Connection string escaping -------------------------------------------
#
# Target credentials are created by the target DBA (OQ-2026-002), so their
# character set is outside WebQuery's control. Interpolating them into a URL
# with an f-string re-parsed 'P@ss/w0rd#1' into host 'ss' and password 'P' —
# sending part of a real password to a host the admin never typed.

SPECIAL_PASSWORD = "P@ss/w0rd#1"


def test_special_characters_in_password_round_trip_for_postgresql():
    from sqlalchemy.engine import make_url

    from database_provider.config import create_connection_string

    url = make_url(
        create_connection_string(
            tech="postgresql",
            driver="asyncpg",
            username="app_rw",
            password=SPECIAL_PASSWORD,
            servername="db.internal",
            database="sales",
        )
    )

    assert url.host == "db.internal"
    assert url.username == "app_rw"
    assert url.password == SPECIAL_PASSWORD
    assert url.database == "sales"


def test_special_characters_in_password_round_trip_for_mssql():
    from sqlalchemy.engine import make_url

    from database_provider.config import create_connection_string

    url = make_url(
        create_connection_string(
            tech="mssql",
            driver="aioodbc",
            username="app_ro",
            password=SPECIAL_PASSWORD,
            servername="sqlhost",
            database="AdventureWorks",
        )
    )

    assert url.host == "sqlhost"
    assert url.password == SPECIAL_PASSWORD
    assert url.query["driver"] == "ODBC Driver 18 for SQL Server"
    assert url.query["TrustServerCertificate"] == "yes"
    assert url.query["connection timeout"] == "30"


def test_special_characters_in_username_and_database_round_trip():
    from sqlalchemy.engine import make_url

    from database_provider.config import create_connection_string

    url = make_url(
        create_connection_string(
            tech="mysql",
            driver="aiomysql",
            username="app@corp",
            password="p/w",
            servername="mysqlhost",
            database="reporting db",
        )
    )

    assert url.username == "app@corp"
    assert url.password == "p/w"
    assert url.database == "reporting db"


def test_host_and_port_are_split():
    from sqlalchemy.engine import make_url

    from database_provider.config import create_connection_string

    url = make_url(
        create_connection_string(
            tech="postgresql",
            driver="asyncpg",
            username="u",
            password="p",
            servername="db.internal:5433",
            database="sales",
        )
    )

    assert url.host == "db.internal"
    assert url.port == 5433


def test_named_sql_server_instance_is_not_treated_as_a_port():
    from sqlalchemy.engine import make_url

    from database_provider.config import create_connection_string

    url = make_url(
        create_connection_string(
            tech="mssql",
            driver="aioodbc",
            username="u",
            password="p",
            servername="SQLHOST\\PROD",
            database="sales",
        )
    )

    assert url.host == "SQLHOST\\PROD"
    assert url.port is None


def test_master_connection_string_is_escaped(monkeypatch):
    from sqlalchemy.engine import make_url

    from database_provider import config

    monkeypatch.setattr(config, "DB_USER", "sa@corp")
    monkeypatch.setattr(config, "DB_PASSWORD", SPECIAL_PASSWORD)

    url = make_url(config.get_master_connection_string("sqlhost"))

    assert url.host == "sqlhost"
    assert url.username == "sa@corp"
    assert url.password == SPECIAL_PASSWORD
    assert url.database == "master"


def test_app_database_url_is_escaped(monkeypatch):
    """The same defect existed in the application metadata database URL."""
    from sqlalchemy.engine import make_url

    monkeypatch.setenv("DB_USER", "app@corp")
    monkeypatch.setenv("DB_PASSWORD", SPECIAL_PASSWORD)
    monkeypatch.setenv("DB_HOST", "appdb.internal")
    monkeypatch.setenv("DB_NAME", "dba_application_db")
    monkeypatch.delenv("APP_DATABASE_URL", raising=False)

    from app_database import config

    config = importlib.reload(config)
    url = make_url(config.DATABASE_URL)

    assert url.host == "appdb.internal"
    assert url.username == "app@corp"
    assert url.password == SPECIAL_PASSWORD
    assert url.database == "dba_application_db"
