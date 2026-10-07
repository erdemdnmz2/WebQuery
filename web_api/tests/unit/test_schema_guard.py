"""The startup guard must refuse to boot on an incomplete schema.

A WebQuery that starts without `uq_server_database` keeps working until two
admins register the same target database; one without `ix_ActionLogging_trace_id`
keeps working until a Slack approval has to find its query. Both failures
surface far from their cause, which is why startup fails closed instead.
"""
import pytest
import sqlalchemy as sa

from app_database.models import Base
from common.schema_guard import verify_schema


@pytest.fixture
def schema_engine():
    engine = sa.create_engine("sqlite://")
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()


def test_complete_schema_starts(schema_engine):
    with schema_engine.connect() as connection:
        verify_schema(connection)  # must not raise


def test_missing_index_stops_startup(schema_engine, caplog):
    with schema_engine.begin() as connection:
        connection.execute(sa.text("DROP INDEX ix_Databases_uuid"))

    with schema_engine.connect() as connection, pytest.raises(SystemExit) as exit_info:
        verify_schema(connection)

    assert exit_info.value.code == 1
    assert "ix_Databases_uuid" in caplog.text
    assert "Alembic" in caplog.text


def test_missing_unique_constraint_stops_startup(schema_engine):
    """`uq_server_database` is the only real guard against a duplicate target."""
    with schema_engine.begin() as connection:
        # SQLite cannot drop a table constraint, so the table is rebuilt
        # without it — the same end state as a create_all() install that
        # predates the constraint.
        connection.execute(sa.text("DROP TABLE Databases"))
        connection.execute(
            sa.text(
                "CREATE TABLE Databases ("
                " id INTEGER NOT NULL PRIMARY KEY,"
                " servername VARCHAR(100) NOT NULL,"
                " database_name VARCHAR(100) NOT NULL,"
                " technology VARCHAR(100) NOT NULL,"
                " username_ro VARCHAR(100), password_ro TEXT,"
                " username_rw VARCHAR(100), password_rw TEXT,"
                " username_ddl VARCHAR(100), password_ddl TEXT,"
                " db_username VARCHAR(100), db_password TEXT,"
                " uuid VARCHAR(36) NOT NULL)"
            )
        )
        connection.execute(sa.text("CREATE INDEX ix_Databases_id ON Databases (id)"))
        connection.execute(sa.text("CREATE INDEX ix_Databases_uuid ON Databases (uuid)"))

    with schema_engine.connect() as connection, pytest.raises(SystemExit):
        verify_schema(connection)


def test_nullable_column_that_must_be_not_null_stops_startup(schema_engine):
    """A nullable Databases.uuid makes the row unaddressable by every API."""
    with schema_engine.begin() as connection:
        connection.execute(sa.text("DROP TABLE Databases"))
        connection.execute(
            sa.text(
                "CREATE TABLE Databases ("
                " id INTEGER NOT NULL PRIMARY KEY,"
                " servername VARCHAR(100) NOT NULL,"
                " database_name VARCHAR(100) NOT NULL,"
                " technology VARCHAR(100) NOT NULL,"
                " uuid VARCHAR(36),"
                " CONSTRAINT uq_server_database UNIQUE (servername, database_name))"
            )
        )
        connection.execute(sa.text("CREATE INDEX ix_Databases_id ON Databases (id)"))
        connection.execute(sa.text("CREATE INDEX ix_Databases_uuid ON Databases (uuid)"))

    with schema_engine.connect() as connection, pytest.raises(SystemExit):
        verify_schema(connection)
