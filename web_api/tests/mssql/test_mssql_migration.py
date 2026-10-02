"""Real SQL Server migration smoke tests for the disposable CI database."""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import URL, make_url

from common.schema_guard import verify_schema

WEB_API_DIR = Path(__file__).resolve().parents[2]
CI_DATABASE = "webquery_ci"


def _validated_ci_url(url: str | None, sentinel: str | None) -> URL:
    """Accept only the disposable database before issuing destructive DDL."""
    if sentinel != "1":
        raise RuntimeError("MSSQL reset requires MSSQL_CI=1.")
    if not url:
        raise RuntimeError("MSSQL reset requires MSSQL_TEST_URL.")

    parsed = make_url(url)
    if parsed.drivername != "mssql+aioodbc" or parsed.database != CI_DATABASE:
        raise RuntimeError(
            f"MSSQL reset only permits the {CI_DATABASE!r} aioodbc database."
        )
    return parsed


def _recreate_database(url: URL) -> None:
    """Drop and create only the hard-coded disposable CI database."""
    admin_url = url.set(drivername="mssql+pyodbc", database="master")
    engine = create_engine(admin_url, isolation_level="AUTOCOMMIT", pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql(
                "IF DB_ID(N'webquery_ci') IS NOT NULL "
                "BEGIN "
                "ALTER DATABASE [webquery_ci] SET SINGLE_USER WITH ROLLBACK IMMEDIATE; "
                "DROP DATABASE [webquery_ci]; "
                "END; "
                "CREATE DATABASE [webquery_ci];"
            )
    finally:
        engine.dispose()


def _migration_head() -> str:
    config = Config(str(WEB_API_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(WEB_API_DIR / "migrations"))
    head = ScriptDirectory.from_config(config).get_current_head()
    assert head is not None
    return head


def _migration_environment(url: URL) -> dict[str, str]:
    environment = os.environ.copy()
    # str(URL) masks the password; only pass this string to the subprocess
    # environment, never to logs or failure messages.
    environment["APP_DATABASE_URL"] = url.render_as_string(hide_password=False)
    return environment


def test_mssql_reset_rejects_non_ci_targets() -> None:
    with pytest.raises(RuntimeError, match="MSSQL_CI"):
        _validated_ci_url(
            "mssql+aioodbc://sa:password@localhost/customer?driver=ODBC+Driver+18+for+SQL+Server",
            None,
        )

    with pytest.raises(RuntimeError, match="webquery_ci"):
        _validated_ci_url(
            "mssql+aioodbc://sa:password@localhost/customer?driver=ODBC+Driver+18+for+SQL+Server",
            "1",
        )


@pytest.mark.skipif(not os.getenv("MSSQL_TEST_URL"), reason="requires the MSSQL CI service")
def test_migrations_and_schema_guard_on_real_mssql() -> None:
    url = _validated_ci_url(os.getenv("MSSQL_TEST_URL"), os.getenv("MSSQL_CI"))
    _recreate_database(url)

    environment = _migration_environment(url)
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=WEB_API_DIR,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr

    engine = create_engine(url.set(drivername="mssql+pyodbc"), pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == _migration_head()
            verify_schema(connection)

            columns = {
                column["name"]: str(column["type"]).upper()
                for column in inspect(connection).get_columns("QueryData")
            }
            assert "UNIQUEIDENTIFIER" in columns["uuid"]

            workspace_columns = {
                column["name"]: str(column["type"]).upper()
                for column in inspect(connection).get_columns("Workspaces")
            }
            assert "NVARCHAR" in workspace_columns["name"]
            assert "NVARCHAR" in workspace_columns["description"]
    finally:
        engine.dispose()
