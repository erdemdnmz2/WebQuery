import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect
from sqlalchemy.dialects import mssql

from app_database.models import Base, Workspace


WEB_API_DIR = Path(__file__).resolve().parents[2]


def _run_upgrade(database_path: Path) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["APP_DATABASE_URL"] = f"sqlite:///{database_path}"
    return subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=WEB_API_DIR,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def test_baseline_migration_creates_a_new_database(tmp_path: Path) -> None:
    result = _run_upgrade(tmp_path / "new.db")

    assert result.returncode == 0, result.stderr


def test_baseline_migration_accepts_a_complete_legacy_schema(tmp_path: Path) -> None:
    database_path = tmp_path / "legacy.db"
    engine = create_engine(f"sqlite:///{database_path}")
    Base.metadata.create_all(engine)
    engine.dispose()

    result = _run_upgrade(database_path)

    assert result.returncode == 0, result.stderr


def test_audit_log_migration_creates_expected_schema(tmp_path: Path) -> None:
    database_path = tmp_path / "audit-log.db"
    result = _run_upgrade(database_path)

    assert result.returncode == 0, result.stderr

    engine = create_engine(f"sqlite:///{database_path}")
    try:
        inspector = inspect(engine)
        assert "AuditLog" in inspector.get_table_names()
        assert {column["name"] for column in inspector.get_columns("AuditLog")} == {
            "id",
            "created_at",
            "actor_user_id",
            "actor_username",
            "actor_slack_id",
            "action",
            "target_type",
            "target_id",
            "details",
            "client_ip",
            "trace_id",
        }
        assert {
            index["name"] for index in inspector.get_indexes("AuditLog")
        } >= {
            "ix_AuditLog_created_at",
            "ix_AuditLog_actor_user_id",
            "ix_AuditLog_action",
            "ix_AuditLog_target_id",
            "ix_AuditLog_trace_id",
        }
    finally:
        engine.dispose()


def test_query_decision_metadata_migration_creates_expected_columns(tmp_path: Path) -> None:
    database_path = tmp_path / "query-decision.db"
    result = _run_upgrade(database_path)

    assert result.returncode == 0, result.stderr

    engine = create_engine(f"sqlite:///{database_path}")
    try:
        inspector = inspect(engine)
        query_data_columns = {
            column["name"] for column in inspector.get_columns("QueryData")
        }
        assert {"decision_reason", "decided_by", "decided_at"} <= query_data_columns
    finally:
        engine.dispose()


def test_workspace_text_columns_are_nvarchar_on_mssql() -> None:
    """The baseline created these as VARCHAR; a3f5c81b9d24 widens them.

    On MSSQL a VARCHAR column is bound to the server codepage, which drops the
    Turkish-specific letters from workspace names. The model declares
    AppNVarChar, and a database built only from the baseline would disagree
    with it, so the type the ORM asks for is asserted here directly.
    """
    dialect = mssql.dialect()

    for column_name in ("name", "description"):
        column = Workspace.__table__.c[column_name]
        rendered = column.type.dialect_impl(dialect).compile(dialect)
        assert rendered.upper().startswith("NVARCHAR"), (
            f"Workspaces.{column_name} compiles to {rendered} on MSSQL"
        )


def test_workspace_nvarchar_migration_is_reachable(tmp_path: Path) -> None:
    """The widening migration must be part of the chain 'upgrade head' walks.

    It is a no-op outside MSSQL, so nothing about the SQLite schema proves it
    ran. What is worth protecting is that it stays wired into the chain.
    """
    result = _run_upgrade(tmp_path / "chain.db")
    assert result.returncode == 0, result.stderr

    history = subprocess.run(
        [sys.executable, "-m", "alembic", "history"],
        cwd=WEB_API_DIR,
        capture_output=True,
        text=True,
        check=False,
    )
    assert history.returncode == 0, history.stderr
    assert "a3f5c81b9d24" in history.stdout
