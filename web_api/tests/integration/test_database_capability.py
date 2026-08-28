"""Contract tests for what the database catalogue tells a query user.

The SQL editor shows one row per registered database with a capability badge.
That badge must describe what this user can actually execute, and must never
carry the target account behind it.
"""
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app import app
from app_database.models import Databases, User, UserDatabaseAssociation


async def _seed_database(servername: str, database_name: str, **credentials) -> tuple[str, int]:
    app_db = app.state.context.app_db
    async with app_db.get_app_db() as db:
        entry = Databases(
            servername=servername,
            database_name=database_name,
            technology="postgresql",
            **credentials,
        )
        db.add(entry)
        await db.commit()
        await db.refresh(entry)
        return entry.uuid, entry.id


async def _register(client: AsyncClient, username: str) -> int:
    email = f"{username}@example.com"
    await client.post("/api/register", json={
        "username": username, "email": email, "password": "StrongPassword123!",
    })
    await client.post("/api/login", json={"email": email, "password": "StrongPassword123!"})
    async with app.state.context.app_db.get_app_db() as db:
        result = await db.execute(select(User).where(User.email == email))
        return result.scalars().first().id


async def _grant(user_id: int, database_id: int, role: str) -> None:
    async with app.state.context.app_db.get_app_db() as db:
        db.add(UserDatabaseAssociation(
            user_id=user_id, database_id=database_id, role=role, is_admin=(role == "ADMIN"),
        ))
        await db.commit()


async def _reload_catalogue() -> None:
    app_db = app.state.context.app_db
    app.state.context.db_provider.set_db_info(await app_db.get_db_info())


@pytest.mark.asyncio
async def test_catalogue_reports_capability_and_never_credentials(async_client: AsyncClient):
    """A read+write database seen by a READER reports `ro`, with no account data."""
    db_uuid, db_id = await _seed_database(
        "cap-server", "cap-db",
        username_ro="cap_ro", password_ro="ro-secret",
        username_rw="cap_rw", password_rw="rw-secret",
    )
    await _reload_catalogue()

    client = AsyncClient(transport=async_client._transport, base_url="http://test")
    user_id = await _register(client, "capreader")
    await _grant(user_id, db_id, "READER")

    response = await client.get("/api/database_information")
    assert response.status_code == 200

    databases = response.json()["db_info"]["cap-server"]["databases"]
    assert len(databases) == 1, "one registration must stay one row, not one row per tier"
    assert databases[0] == {"name": "cap-db", "uuid": db_uuid, "capability": "ro"}

    # Belt and braces: no tier account may appear anywhere in the payload.
    body = response.text
    for secret in ("cap_ro", "ro-secret", "cap_rw", "rw-secret", "connection_mode"):
        assert secret not in body


@pytest.mark.asyncio
async def test_catalogue_capability_follows_the_users_role(async_client: AsyncClient):
    """The same registration reports a wider capability to a WRITER."""
    _db_uuid, db_id = await _seed_database(
        "cap-server-2", "cap-db-2",
        username_ro="w_ro", password_ro="ro-secret",
        username_rw="w_rw", password_rw="rw-secret",
    )
    await _reload_catalogue()

    client = AsyncClient(transport=async_client._transport, base_url="http://test")
    user_id = await _register(client, "capwriter")
    await _grant(user_id, db_id, "WRITER")

    response = await client.get("/api/database_information")
    databases = response.json()["db_info"]["cap-server-2"]["databases"]
    assert databases[0]["capability"] == "ro_rw"


@pytest.mark.asyncio
async def test_catalogue_capability_is_capped_by_the_registration(async_client: AsyncClient):
    """An ADMIN on a read-only registration still reports `ro`, not `ro_rw_ddl`."""
    _db_uuid, db_id = await _seed_database(
        "cap-server-3", "cap-db-3", username_ro="a_ro", password_ro="ro-secret",
    )
    await _reload_catalogue()

    client = AsyncClient(transport=async_client._transport, base_url="http://test")
    user_id = await _register(client, "capadmin")
    await _grant(user_id, db_id, "ADMIN")

    response = await client.get("/api/database_information")
    databases = response.json()["db_info"]["cap-server-3"]["databases"]
    assert databases[0]["capability"] == "ro"


@pytest.mark.asyncio
async def test_grant_is_rejected_when_the_database_lacks_the_tier(async_client: AsyncClient):
    """Granting WRITER on a read-only registration fails at grant time."""
    _db_uuid, db_id = await _seed_database(
        "grant-server", "grant-db", username_ro="g_ro", password_ro="ro-secret",
    )
    await _reload_catalogue()

    admin_client = AsyncClient(transport=async_client._transport, base_url="http://test")
    admin_id = await _register(admin_client, "grantadmin")
    await _grant(admin_id, db_id, "ADMIN")

    member_client = AsyncClient(transport=async_client._transport, base_url="http://test")
    member_id = await _register(member_client, "grantmember")

    response = await admin_client.post("/api/admin/associate_user", json={
        "user_id": member_id, "database_id": db_id, "role": "WRITER",
    })
    assert response.status_code == 400
    assert "RW" in response.text

    # The rejected grant must not have been written.
    async with app.state.context.app_db.get_app_db() as db:
        result = await db.execute(select(UserDatabaseAssociation).where(
            UserDatabaseAssociation.user_id == member_id,
            UserDatabaseAssociation.database_id == db_id,
        ))
        assert result.scalars().first() is None


@pytest.mark.asyncio
async def test_grant_is_accepted_when_the_registration_provisions_the_tier(async_client: AsyncClient):
    """The same WRITER grant succeeds once the registration carries an rw account."""
    _db_uuid, db_id = await _seed_database(
        "grant-server-2", "grant-db-2",
        username_ro="g2_ro", password_ro="ro-secret",
        username_rw="g2_rw", password_rw="rw-secret",
    )
    await _reload_catalogue()

    admin_client = AsyncClient(transport=async_client._transport, base_url="http://test")
    admin_id = await _register(admin_client, "grantadmin2")
    await _grant(admin_id, db_id, "ADMIN")

    member_client = AsyncClient(transport=async_client._transport, base_url="http://test")
    member_id = await _register(member_client, "grantmember2")

    response = await admin_client.post("/api/admin/associate_user", json={
        "user_id": member_id, "database_id": db_id, "role": "WRITER",
    })
    assert response.status_code == 200
