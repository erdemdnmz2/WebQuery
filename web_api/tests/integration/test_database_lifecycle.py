"""
Integration tests for target database registration lifecycle (P1-10).

Registration used to be add-and-read only. A DBA rotating `app_rw` on the target
server had no way to tell WebQuery, and the record could not be deleted and
re-added either — `(servername, database_name)` is unique — so the only remedy
was editing the metadata database by hand. `AuditAction.REMOVE_DATABASE` existed
with no call site.

Decisions under test: OQ-2026-016 (soft delete), OQ-2026-017 (identity change
carries saved queries), OQ-2026-018 (narrowing refused, conflicts listed),
OQ-2026-019 (PATCH semantics).
"""
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app import app
from app_database.models import (
    AuditLog,
    Databases,
    MaskingRule,
    QueryData,
    User,
    UserDatabaseAssociation,
    Workspace,
)
from common.audit_actions import AuditAction

PASSWORD = "StrongPassword123!"


def _client(async_client: AsyncClient) -> AsyncClient:
    return AsyncClient(transport=async_client._transport, base_url="http://test")


async def _register(async_client: AsyncClient, email: str, username: str) -> int:
    await async_client.post(
        "/api/register",
        json={"username": username, "email": email, "password": PASSWORD},
    )
    async with app.state.context.app_db.get_app_db() as db:
        return (
            (await db.execute(select(User).where(User.email == email)))
            .scalars()
            .first()
            .id
        )


async def _owner_client(async_client: AsyncClient) -> tuple[AsyncClient, int]:
    owner_id = await _register(async_client, "lifecycle-owner@example.com", "lcowner")
    async with app.state.context.app_db.get_app_db() as db:
        owner = await db.get(User, owner_id)
        owner.is_platform_owner = True
        await db.commit()
    client = _client(async_client)
    await client.post(
        "/api/login",
        json={"email": "lifecycle-owner@example.com", "password": PASSWORD},
    )
    return client, owner_id


async def _add_database(owner_client: AsyncClient, admin_id: int, mode: str = "ro_rw"):
    payload = {
        "servername": "prod-sql",
        "database_name": "SalesDB",
        "tech_name": "postgresql",
        "connection_mode": mode,
        "initial_admin_user_id": admin_id,
        "username_ro": "app_ro",
        "password_ro": "ro-secret",
    }
    if mode != "ro":
        payload |= {"username_rw": "app_rw", "password_rw": "rw-secret"}
    if mode == "ro_rw_ddl":
        payload |= {"username_ddl": "app_ddl", "password_ddl": "ddl-secret"}
    response = await owner_client.post("/api/owner/databases", json=payload)
    assert response.status_code == 201, response.text

    async with app.state.context.app_db.get_app_db() as db:
        database = (
            await db.execute(select(Databases).where(Databases.database_name == "SalesDB"))
        ).scalars().first()
        return database.id


async def _read(database_id: int) -> Databases:
    async with app.state.context.app_db.get_app_db() as db:
        return await db.get(Databases, database_id)


# --- OQ-2026-019: PATCH semantics ------------------------------------------


@pytest.mark.asyncio
async def test_rotating_one_password_leaves_the_other_tiers_alone(
    async_client: AsyncClient,
):
    owner_client, owner_id = await _owner_client(async_client)
    database_id = await _add_database(owner_client, owner_id)

    response = await owner_client.patch(
        f"/api/owner/databases/{database_id}", json={"password_rw": "rotated-secret"}
    )
    assert response.status_code == 200
    assert response.json()["updated_tiers"] == ["rw"]

    database = await _read(database_id)
    assert database.password_rw == "rotated-secret"
    assert database.password_ro == "ro-secret"  # untouched
    assert database.username_ro == "app_ro"
    assert database.username_rw == "app_rw"


@pytest.mark.asyncio
async def test_empty_update_body_is_rejected(async_client: AsyncClient):
    owner_client, owner_id = await _owner_client(async_client)
    database_id = await _add_database(owner_client, owner_id)

    response = await owner_client.patch(f"/api/owner/databases/{database_id}", json={})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_unknown_field_is_rejected(async_client: AsyncClient):
    owner_client, owner_id = await _owner_client(async_client)
    database_id = await _add_database(owner_client, owner_id)

    response = await owner_client.patch(
        f"/api/owner/databases/{database_id}", json={"technology": "mysql"}
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_widening_the_mode_adds_a_tier(async_client: AsyncClient):
    owner_client, owner_id = await _owner_client(async_client)
    database_id = await _add_database(owner_client, owner_id, mode="ro")

    response = await owner_client.patch(
        f"/api/owner/databases/{database_id}",
        json={
            "connection_mode": "ro_rw",
            "username_rw": "app_rw",
            "password_rw": "rw-secret",
        },
    )
    assert response.status_code == 200
    assert response.json()["connection_mode"] == "ro_rw"


# --- OQ-2026-018: narrowing is refused, conflicts listed --------------------


@pytest.mark.asyncio
async def test_narrowing_is_refused_while_a_writer_exists(async_client: AsyncClient):
    owner_client, owner_id = await _owner_client(async_client)
    database_id = await _add_database(owner_client, owner_id)
    writer_id = await _register(async_client, "writer@example.com", "writerone")
    async with app.state.context.app_db.get_app_db() as db:
        db.add(
            UserDatabaseAssociation(
                user_id=writer_id, database_id=database_id, role="WRITER", is_admin=False
            )
        )
        await db.commit()

    response = await owner_client.patch(
        f"/api/owner/databases/{database_id}", json={"connection_mode": "ro"}
    )

    assert response.status_code == 409
    body = response.json()
    assert body["error_code"] == "CONNECTION_MODE_CONFLICT"
    assert body["conflicts"] == [
        {
            "user_id": writer_id,
            "username": "writerone",
            "role": "WRITER",
            "unsupported_tier": "rw",
        }
    ]

    # Nothing was changed by the refused request.
    database = await _read(database_id)
    assert database.username_rw == "app_rw"


@pytest.mark.asyncio
async def test_narrowing_succeeds_once_the_conflicting_grant_is_gone(
    async_client: AsyncClient,
):
    owner_client, owner_id = await _owner_client(async_client)
    database_id = await _add_database(owner_client, owner_id)

    response = await owner_client.patch(
        f"/api/owner/databases/{database_id}", json={"connection_mode": "ro"}
    )
    assert response.status_code == 200
    assert response.json()["connection_mode"] == "ro"

    database = await _read(database_id)
    assert database.username_rw is None
    assert database.password_rw is None
    assert database.username_ro == "app_ro"


# --- OQ-2026-017: identity change carries saved queries ---------------------


@pytest.mark.asyncio
async def test_renaming_moves_saved_queries_with_the_registration(
    async_client: AsyncClient,
):
    owner_client, owner_id = await _owner_client(async_client)
    database_id = await _add_database(owner_client, owner_id)

    app_db = app.state.context.app_db
    async with app_db.get_app_db() as db:
        query = QueryData(
            user_id=owner_id,
            servername="prod-sql",
            database_name="SalesDB",
            query="SELECT 1",
            uuid="lifecycle-query",
            status="saved_in_workspace",
        )
        db.add(query)
        await db.flush()
        db.add(Workspace(name="Saved", user_id=owner_id, query_id=query.id))
        await db.commit()

    response = await owner_client.patch(
        f"/api/owner/databases/{database_id}", json={"servername": "prod-sql-01"}
    )
    assert response.status_code == 200

    async with app_db.get_app_db() as db:
        moved = (
            await db.execute(select(QueryData).where(QueryData.uuid == "lifecycle-query"))
        ).scalars().first()
        assert moved.servername == "prod-sql-01"
        assert moved.database_name == "SalesDB"

    # The saved workspace still resolves to a database.
    workspaces = (await owner_client.get("/api/workspaces")).json()["workspaces"]
    assert workspaces[0]["db_uuid"] != ""
    assert workspaces[0]["servername"] == "prod-sql-01"


@pytest.mark.asyncio
async def test_renaming_onto_an_existing_registration_is_refused(
    async_client: AsyncClient,
):
    owner_client, owner_id = await _owner_client(async_client)
    database_id = await _add_database(owner_client, owner_id)
    async with app.state.context.app_db.get_app_db() as db:
        db.add(
            Databases(
                servername="prod-sql", database_name="OtherDB", technology="postgresql"
            )
        )
        await db.commit()

    response = await owner_client.patch(
        f"/api/owner/databases/{database_id}", json={"database_name": "OtherDB"}
    )
    assert response.status_code == 400
    assert response.json()["error_code"] == "DATABASE_ALREADY_EXISTS"


# --- OQ-2026-016: soft delete ----------------------------------------------


@pytest.mark.asyncio
async def test_retiring_preserves_every_dependent_row(async_client: AsyncClient):
    owner_client, owner_id = await _owner_client(async_client)
    database_id = await _add_database(owner_client, owner_id)
    app_db = app.state.context.app_db
    async with app_db.get_app_db() as db:
        db.add(
            MaskingRule(
                database_id=database_id,
                table_name="Customers",
                column_name="email",
                masking_type="full",
                is_active=True,
            )
        )
        await db.commit()

    response = await owner_client.delete(f"/api/owner/databases/{database_id}")
    assert response.status_code == 200

    async with app_db.get_app_db() as db:
        database = await db.get(Databases, database_id)
        assert database is not None
        assert database.is_active is False
        assert database.retired_at is not None
        assert database.retired_by == "lcowner"

        # Nothing was deleted.
        assert (
            await db.execute(
                select(MaskingRule).where(MaskingRule.database_id == database_id)
            )
        ).scalars().all()
        assert (
            await db.execute(
                select(UserDatabaseAssociation).where(
                    UserDatabaseAssociation.database_id == database_id
                )
            )
        ).scalars().all()

        audit = (
            await db.execute(
                select(AuditLog).where(AuditLog.action == AuditAction.REMOVE_DATABASE)
            )
        ).scalars().all()
        assert len(audit) == 1
        assert audit[0].target_id == str(database_id)
        # Credential values never enter an audit record.
        assert "ro-secret" not in (audit[0].details or "")


@pytest.mark.asyncio
async def test_retired_database_leaves_the_runtime_catalogue(async_client: AsyncClient):
    owner_client, owner_id = await _owner_client(async_client)
    database_id = await _add_database(owner_client, owner_id)
    db_uuid = str((await _read(database_id)).uuid)
    assert db_uuid in app.state.context.db_provider.db_by_uuid

    await owner_client.delete(f"/api/owner/databases/{database_id}")

    assert db_uuid not in app.state.context.db_provider.db_by_uuid
    assert (await owner_client.get("/api/owner/databases")).json() == []


@pytest.mark.asyncio
async def test_re_registering_revives_the_retired_record(async_client: AsyncClient):
    """(servername, database_name) is unique, so this must reuse the row."""
    owner_client, owner_id = await _owner_client(async_client)
    database_id = await _add_database(owner_client, owner_id)
    original_uuid = str((await _read(database_id)).uuid)
    await owner_client.delete(f"/api/owner/databases/{database_id}")

    revived_id = await _add_database(owner_client, owner_id)

    assert revived_id == database_id
    database = await _read(database_id)
    assert database.is_active is True
    assert database.retired_at is None
    assert str(database.uuid) == original_uuid


@pytest.mark.asyncio
async def test_update_of_a_retired_database_is_not_found(async_client: AsyncClient):
    owner_client, owner_id = await _owner_client(async_client)
    database_id = await _add_database(owner_client, owner_id)
    await owner_client.delete(f"/api/owner/databases/{database_id}")

    response = await owner_client.patch(
        f"/api/owner/databases/{database_id}", json={"password_ro": "x"}
    )
    assert response.status_code == 404


# --- Authorization ----------------------------------------------------------


@pytest.mark.asyncio
async def test_lifecycle_endpoints_require_platform_owner(async_client: AsyncClient):
    owner_client, owner_id = await _owner_client(async_client)
    database_id = await _add_database(owner_client, owner_id)

    await _register(async_client, "not-owner@example.com", "notowner")
    intruder = _client(async_client)
    await intruder.post(
        "/api/login", json={"email": "not-owner@example.com", "password": PASSWORD}
    )

    assert (
        await intruder.patch(
            f"/api/owner/databases/{database_id}", json={"password_ro": "x"}
        )
    ).status_code == 403
    assert (
        await intruder.delete(f"/api/owner/databases/{database_id}")
    ).status_code == 403


@pytest.mark.asyncio
async def test_update_writes_an_audit_record_without_credential_values(
    async_client: AsyncClient,
):
    owner_client, owner_id = await _owner_client(async_client)
    database_id = await _add_database(owner_client, owner_id)

    await owner_client.patch(
        f"/api/owner/databases/{database_id}",
        json={"password_rw": "a-brand-new-secret"},
    )

    async with app.state.context.app_db.get_app_db() as db:
        audit = (
            await db.execute(
                select(AuditLog).where(AuditLog.action == AuditAction.UPDATE_DATABASE)
            )
        ).scalars().all()
        assert len(audit) == 1
        details = audit[0].details or ""
        assert "a-brand-new-secret" not in details
        assert "ro-secret" not in details
        assert '"rw"' in details  # which tier changed, not what it changed to
