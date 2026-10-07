"""Regression coverage for SPEC-0020 centralized safe logging."""
import ast
import logging
from pathlib import Path

from common.logging_config import configured_log_level
from database_provider.database import DatabaseProvider


def test_log_level_resolves_and_invalid_value_falls_back_to_info():
    assert configured_log_level("debug") == logging.DEBUG
    assert configured_log_level("WARNING") == logging.WARNING
    assert configured_log_level("not-a-level") == logging.INFO


def test_production_python_modules_do_not_call_print():
    web_api_root = Path(__file__).parents[2]
    excluded_parts = {"tests", "migrations", "__pycache__"}

    for path in web_api_root.rglob("*.py"):
        if excluded_parts.intersection(path.relative_to(web_api_root).parts):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        print_calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "print"
        ]
        assert not print_calls, f"print() remains: {path}"


def test_db_catalog_debug_log_excludes_credentials_and_configuration(caplog):
    provider = DatabaseProvider()
    catalogue = {
        "internal-sql.example": {
            "technology": "postgresql",
            "databases": [
                {
                    "name": "finance",
                    "uuid": "db-1",
                    "credentials": {
                        "ro": {"username": "finance_ro", "password": "secret-value"}
                    },
                }
            ],
        }
    }

    with caplog.at_level(logging.DEBUG, logger="database_provider.database"):
        provider.set_db_info(catalogue)

    assert "1 servers, 1 databases" in caplog.text
    for sensitive_value in ("internal-sql.example", "finance", "finance_ro", "secret-value", "db-1"):
        assert sensitive_value not in caplog.text


def test_bootstrap_engine_sql_echo_is_disabled():
    source = (Path(__file__).parents[2] / "create_db.py").read_text(encoding="utf-8")
    assert "create_engine(sa_url, echo=False" in source
