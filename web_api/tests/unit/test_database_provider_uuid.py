"""
Regression tests for UUID key normalisation in DatabaseProvider.

The MSSQL UNIQUEIDENTIFIER column behind `Databases.uuid` is returned by the ORM
as a `uuid.UUID` instance, while every lookup (request bodies, workspace rows)
carries the value as a string. `db_by_uuid` is declared `Dict[str, ...]`, so the
provider is responsible for normalising the key. Before this was enforced, every
`execute_query` call failed with "Database with UUID '...' not found" because
`'<uuid>' in {UUID('<uuid>'): ...}` is False.

The existing integration tests miss this: they call `set_db_info` with
hand-built dictionaries whose uuids are already strings, so the ORM's actual
return type is never exercised.
"""
import os
import sys
import uuid

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from database_provider.database import DatabaseProvider

DB_UUID = uuid.UUID("00f3adc3-d10c-4a27-a5ab-00f63af73ec8")


def info_as_orm_returns_it():
    """Mirror `AppDatabase.get_db_info()`, which passes `Databases.uuid` through untouched."""
    return {
        "db": {
            "databases": [{"name": "AdventureWorksLT", "uuid": DB_UUID}],
            "technology": "mssql",
        }
    }


def test_uuid_objects_are_normalised_to_string_keys():
    provider = DatabaseProvider()
    provider.set_db_info(info_as_orm_returns_it())

    assert list(provider.db_by_uuid) == [str(DB_UUID)]
    assert all(isinstance(key, str) for key in provider.db_by_uuid)


def test_string_lookup_matches_uuid_sourced_entry():
    """The failure mode that broke execute_query: string lookup against a UUID key."""
    provider = DatabaseProvider()
    provider.set_db_info(info_as_orm_returns_it())

    assert str(DB_UUID) in provider.db_by_uuid
    entry = provider.db_by_uuid[str(DB_UUID)]
    assert entry["servername"] == "db"
    assert entry["database_name"] == "AdventureWorksLT"
    assert entry["technology"] == "mssql"


def test_string_uuids_are_left_unchanged():
    """Callers that already pass strings (the integration fixtures) must keep working."""
    provider = DatabaseProvider()
    provider.set_db_info(
        {"db": {"databases": [{"name": "Satis", "uuid": str(DB_UUID)}], "technology": "mssql"}}
    )

    assert str(DB_UUID) in provider.db_by_uuid


def test_set_db_info_replaces_previous_mapping():
    """`add_database` re-runs set_db_info; stale uuids must not survive."""
    provider = DatabaseProvider()
    provider.set_db_info(info_as_orm_returns_it())
    provider.set_db_info({"db": {"databases": [], "technology": "mssql"}})

    assert provider.db_by_uuid == {}


@pytest.mark.asyncio
async def test_get_session_rejects_unknown_uuid():
    provider = DatabaseProvider()
    provider.set_db_info(info_as_orm_returns_it())

    with pytest.raises(ValueError, match="not found in configuration"):
        async with provider.get_session(user=None, db_uuid=str(uuid.uuid4())):
            pass
