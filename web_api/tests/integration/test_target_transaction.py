"""
Regression tests for target database transaction durability.

`DatabaseProvider.get_session` used to open the target session with
`autocommit=False`, never call `commit()`, and close the session on exit.
SQLAlchemy rolls an open transaction back on close, so an INSERT/UPDATE/DELETE
ran, reported a rowcount and was audited as successful — then vanished.

The existing suite could not catch this: `tests/conftest.py` mocks the target
session, so `rowcount` comes from a stub and nothing is ever written. These
tests therefore drive a *real* engine (aiosqlite on a temp file) through the
provider, and read the row back over a second, independent session.

See docs/inbox/TARGET-TRANSACTION-COMMIT.md.
"""
import os
import sys
import uuid

import pytest
from sqlalchemy import text

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app_database.models import User
from database_provider import database as database_module
from database_provider.database import DatabaseProvider

DB_UUID = str(uuid.uuid4())

pytestmark = pytest.mark.asyncio


@pytest.fixture
def sqlite_provider(tmp_path, monkeypatch):
    """A DatabaseProvider whose single registered target is a real sqlite file."""
    db_file = tmp_path / "target.db"
    url = f"sqlite+aiosqlite:///{db_file}"

    # The provider builds a driver-specific URL for mssql/mysql/postgresql. The
    # transaction behaviour under test is driver-independent, so the URL builder
    # and its timeout connect args are swapped for a sqlite equivalent.
    monkeypatch.setattr(
        database_module, "create_connection_string", lambda **_kwargs: url
    )
    monkeypatch.setattr(database_module, "get_connect_args", lambda *_a, **_k: {})

    provider = DatabaseProvider()
    provider.set_db_info(
        {
            "localhost": {
                "technology": "sqlite",
                "databases": [
                    {
                        "name": "target",
                        "uuid": DB_UUID,
                        "connection_mode": "ro_rw",
                        "credentials": {
                            "ro": {"username": "ro_user", "password": "ro_pass"},
                            "rw": {"username": "rw_user", "password": "rw_pass"},
                        },
                    }
                ],
            }
        }
    )
    return provider


@pytest.fixture
def target_user():
    return User(id=1, username="writer", email="writer@example.com")


async def _create_table(provider, user):
    async with provider.get_session(user=user, db_uuid=DB_UUID, tier="rw") as session:
        await session.execute(text("CREATE TABLE widgets (id INTEGER PRIMARY KEY, name TEXT)"))


async def _read_names(provider, user):
    async with provider.get_session(user=user, db_uuid=DB_UUID, tier="ro") as session:
        result = await session.execute(text("SELECT name FROM widgets ORDER BY id"))
        return [row[0] for row in result.fetchall()]


async def test_rw_insert_survives_session_close(sqlite_provider, target_user):
    """The core defect: a write reported as successful must still be there."""
    await _create_table(sqlite_provider, target_user)

    async with sqlite_provider.get_session(
        user=target_user, db_uuid=DB_UUID, tier="rw"
    ) as session:
        result = await session.execute(
            text("INSERT INTO widgets (id, name) VALUES (1, 'first')")
        )
        assert result.rowcount == 1

    assert await _read_names(sqlite_provider, target_user) == ["first"]


async def test_rw_update_and_delete_survive_session_close(sqlite_provider, target_user):
    await _create_table(sqlite_provider, target_user)
    async with sqlite_provider.get_session(
        user=target_user, db_uuid=DB_UUID, tier="rw"
    ) as session:
        await session.execute(
            text("INSERT INTO widgets (id, name) VALUES (1, 'a'), (2, 'b')")
        )

    async with sqlite_provider.get_session(
        user=target_user, db_uuid=DB_UUID, tier="rw"
    ) as session:
        await session.execute(text("UPDATE widgets SET name = 'renamed' WHERE id = 1"))
    assert await _read_names(sqlite_provider, target_user) == ["renamed", "b"]

    async with sqlite_provider.get_session(
        user=target_user, db_uuid=DB_UUID, tier="rw"
    ) as session:
        await session.execute(text("DELETE FROM widgets WHERE id = 2"))
    assert await _read_names(sqlite_provider, target_user) == ["renamed"]


async def test_failure_inside_the_block_rolls_the_batch_back(sqlite_provider, target_user):
    """A raised exception must discard everything the block wrote."""
    await _create_table(sqlite_provider, target_user)

    with pytest.raises(RuntimeError):
        async with sqlite_provider.get_session(
            user=target_user, db_uuid=DB_UUID, tier="rw"
        ) as session:
            await session.execute(
                text("INSERT INTO widgets (id, name) VALUES (1, 'doomed')")
            )
            raise RuntimeError("execution failed after the write")

    assert await _read_names(sqlite_provider, target_user) == []


async def test_ro_tier_never_commits(sqlite_provider, target_user):
    """`ro` is read-only by construction; nothing it touches may persist."""
    await _create_table(sqlite_provider, target_user)

    async with sqlite_provider.get_session(
        user=target_user, db_uuid=DB_UUID, tier="ro"
    ) as session:
        await session.execute(text("INSERT INTO widgets (id, name) VALUES (9, 'leak')"))

    assert await _read_names(sqlite_provider, target_user) == []


async def test_rows_are_readable_inside_the_block_on_a_write_tier(
    sqlite_provider, target_user
):
    """RETURNING-style reads must still work: the commit happens after the block."""
    await _create_table(sqlite_provider, target_user)
    async with sqlite_provider.get_session(
        user=target_user, db_uuid=DB_UUID, tier="rw"
    ) as session:
        await session.execute(text("INSERT INTO widgets (id, name) VALUES (1, 'x')"))
        result = await session.execute(text("SELECT name FROM widgets"))
        assert [row[0] for row in result.fetchall()] == ["x"]

    assert await _read_names(sqlite_provider, target_user) == ["x"]
