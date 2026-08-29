"""
Regression tests for the create_db.py bootstrap hardening (P1-13).

Two independent defects existed:

1. `create_db.py` caught every exception and returned normally (exit 0), so
   entrypoint.sh's retry loop always saw "success" on the first attempt even
   against an unreachable SQL Server, and `alembic upgrade head` then failed
   immediately after. Readiness is now `wait_for_db.py`'s job, and it reports
   truthfully via its exit code.

2. `target_user` and `target_password` (sourced from DB_USER/DB_PASSWORD env
   vars) were interpolated directly into `CREATE LOGIN ... WITH PASSWORD =
   '...'` and `CREATE USER ...` — an env value containing a SQL identifier
   break-out or an unescaped quote in the password could inject SQL into the
   bootstrap.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from create_db import _escape_literal, _validate_identifier


def test_ordinary_identifier_is_accepted():
    assert _validate_identifier("webquery_app", "field") == "webquery_app"
    assert _validate_identifier("_leading_underscore", "field") == "_leading_underscore"


@pytest.mark.parametrize(
    "hostile",
    [
        "app]; DROP TABLE Users; --",
        "app'; DROP LOGIN sa; --",
        "app WITH PASSWORD",
        "app]--",
        "",
        "123startswithdigit",
        "has space",
        "has-hyphen",
    ],
)
def test_identifiers_that_could_break_out_of_ddl_are_rejected(hostile):
    with pytest.raises(ValueError, match="güvenli bir SQL tanımlayıcı değil"):
        _validate_identifier(hostile, "field")


def test_password_quote_is_escaped_for_the_literal():
    """A password containing a quote must not be able to close the literal early."""
    hostile_password = "abc'; DROP LOGIN sa; --"
    escaped = _escape_literal(hostile_password)

    assert "''" in escaped
    # No lone, unescaped single quote remains that could terminate the literal.
    assert escaped.replace("''", "") .count("'") == 0


def test_password_without_special_characters_is_unchanged():
    assert _escape_literal("OrdinaryPassword123!") == "OrdinaryPassword123!"


def test_bootstrap_refuses_a_hostile_db_user_before_touching_the_network(monkeypatch):
    """The identifier is validated before any engine is created."""
    import create_db

    monkeypatch.setattr(
        create_db,
        "DATABASE_URL",
        "mssql+pyodbc://app_user; DROP LOGIN sa; --:password@localhost/app_db"
        "?driver=ODBC+Driver+18+for+SQL+Server",
    )

    def _fail_if_called(*_args, **_kwargs):
        raise AssertionError("create_engine must not run before identifier validation")

    monkeypatch.setattr(create_db, "create_engine", _fail_if_called)

    with pytest.raises(ValueError):
        create_db.create_database_and_user_if_not_exists()
