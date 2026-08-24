import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect

from app_database.models import Base


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
