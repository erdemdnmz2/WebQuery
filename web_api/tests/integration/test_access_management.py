"""
Integration tests for the access-management flows the audit found missing.

P1-7: a database ADMIN had no way to learn a `user_id`, so
`POST /api/admin/associate_user` — the only route to granting query access —
could not be used from the interface. An activated user could reach no database
at all.

P1-8: `AuditAction.REVOKE_DATABASE_ACCESS` had no call site because nothing
could take access away. The only way to cut off a departing employee was to
disable their account everywhere.

P1-9: there was no password change endpoint and no reset, so a password known to
be compromised could not be replaced. `AuditAction.PASSWORD_CHANGED` was
likewise unused.
"""
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app import app
from app_database.models import (
    AuditLog,
    Databases,
    User,
    UserDatabaseAssociation,
    UserSession,
)
from common.audit_actions import AuditAction

PASSWORD = "StrongPassword123!"


async def _register(async_client: AsyncClient, email: str, username: str) -> int:
    await async_client.post(
        "/api/register",
        json={"username": username, "email": email, "password": PASSWORD},
    )
    async with app.state.context.app_db.get_app_db() as db:
        user = (
            await db.execute(select(User).where(User.email == email))
        ).scalars().first()
        return user.id


async def _login(client: AsyncClient, email: str) -> None:
    await client.post("/api/login", json={"email": email, "password": PASSWORD})


def _client(async_client: AsyncClient) -> AsyncClient:
    return AsyncClient(transport=async_client._transport, base_url="http://test")


async def _seed(async_client: AsyncClient, mode: str = "ro_rw"):
    """One database, one ADMIN of it, and one unassociated member."""
    app_db = app.state.context.app_db
    async with app_db.get_app_db() as db:
        database = Databases(
            servername="access-server",
            database_name="access-db",
            technology="postgresql",
            username_ro="app_ro",
            password_ro="ro-secret",
            username_rw="app_rw" if mode != "ro" else None,
            password_rw="rw-secret" if mode != "ro" else None,
        )
        db.add(database)
        await db.commit()
        await db.refresh(database)
        database_id = database.id

    admin_id = await _register(async_client, "dbadmin@example.com", "dbadmin")
    member_id = await _register(async_client, "member@example.com", "member")

    async with app_db.get_app_db() as db:
        db.add(
            UserDatabaseAssociation(
                user_id=admin_id, database_id=database_id, role="ADMIN", is_admin=True
            )
        )
        await db.commit()

    admin_client = _client(async_client)
    await _login(admin_client, "dbadmin@example.com")
    return database_id, admin_id, member_id, admin_client


# --- P1-7 -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_database_admin_can_list_members_and_candidates(async_client: AsyncClient):
    database_id, admin_id, member_id, admin_client = await _seed(async_client)

    response = await admin_client.get(f"/api/admin/databases/{database_id}/users")
    assert response.status_code == 200
    body = response.json()

    assert body["connection_mode"] == "ro_rw"
    assert [member["user_id"] for member in body["members"]] == [admin_id]
    assert body["members"][0]["is_admin"] is True

    # The unassociated member is offered as a grant candidate, by name only.
    candidate_ids = {candidate["user_id"] for candidate in body["candidates"]}
    assert member_id in candidate_ids
    candidate = next(c for c in body["candidates"] if c["user_id"] == member_id)
    assert set(candidate) == {"user_id", "username", "email"}


@pytest.mark.asyncio
async def test_non_admin_of_that_database_cannot_list_its_users(async_client: AsyncClient):
    database_id, _admin_id, _member_id, _admin_client = await _seed(async_client)

    # ADMIN elsewhere is not ADMIN here.
    outsider_id = await _register(async_client, "elsewhere@example.com", "elsewhere")
    app_db = app.state.context.app_db
    async with app_db.get_app_db() as db:
        other = Databases(
            servername="other-server", database_name="other-db", technology="postgresql"
        )
        db.add(other)
        await db.commit()
        await db.refresh(other)
        db.add(
            UserDatabaseAssociation(
                user_id=outsider_id, database_id=other.id, role="ADMIN", is_admin=True
            )
        )
        await db.commit()

    outsider_client = _client(async_client)
    await _login(outsider_client, "elsewhere@example.com")

    response = await outsider_client.get(f"/api/admin/databases/{database_id}/users")
    assert response.status_code == 403
    assert response.json()["error_code"] == "DATABASE_ADMIN_REQUIRED"


@pytest.mark.asyncio
async def test_grant_then_the_member_appears_with_their_role(async_client: AsyncClient):
    database_id, _admin_id, member_id, admin_client = await _seed(async_client)

    granted = await admin_client.post(
        "/api/admin/associate_user",
        json={"user_id": member_id, "database_id": database_id, "role": "WRITER"},
    )
    assert granted.status_code == 200

    body = (await admin_client.get(f"/api/admin/databases/{database_id}/users")).json()
    member = next(m for m in body["members"] if m["user_id"] == member_id)
    assert member["role"] == "WRITER"
    assert member["is_admin"] is False
    assert member_id not in {c["user_id"] for c in body["candidates"]}


# --- P1-8 -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_revoke_removes_access_and_writes_the_audit_record(async_client: AsyncClient):
    database_id, _admin_id, member_id, admin_client = await _seed(async_client)
    await admin_client.post(
        "/api/admin/associate_user",
        json={"user_id": member_id, "database_id": database_id, "role": "WRITER"},
    )

    response = await admin_client.delete(
        f"/api/admin/databases/{database_id}/users/{member_id}"
    )
    assert response.status_code == 200
    assert response.json()["remaining_role"] is None

    app_db = app.state.context.app_db
    async with app_db.get_app_db() as db:
        assert (
            await db.execute(
                select(UserDatabaseAssociation).where(
                    UserDatabaseAssociation.user_id == member_id,
                    UserDatabaseAssociation.database_id == database_id,
                )
            )
        ).scalars().first() is None

        audit = (
            await db.execute(
                select(AuditLog).where(
                    AuditLog.action == AuditAction.REVOKE_DATABASE_ACCESS
                )
            )
        ).scalars().all()
        assert len(audit) == 1
        assert audit[0].target_id == str(member_id)
        assert "WRITER" in audit[0].details


@pytest.mark.asyncio
async def test_revoked_user_can_no_longer_query(async_client: AsyncClient):
    database_id, _admin_id, member_id, admin_client = await _seed(async_client)
    await admin_client.post(
        "/api/admin/associate_user",
        json={"user_id": member_id, "database_id": database_id, "role": "READER"},
    )
    app_db = app.state.context.app_db
    app.state.context.db_provider.set_db_info(await app_db.get_db_info())
    async with app_db.get_app_db() as db:
        db_uuid = str(
            (await db.execute(select(Databases).where(Databases.id == database_id)))
            .scalars()
            .first()
            .uuid
        )

    member_client = _client(async_client)
    await _login(member_client, "member@example.com")
    assert (await member_client.get("/api/database_information")).json()["db_info"]

    await admin_client.delete(f"/api/admin/databases/{database_id}/users/{member_id}")

    denied = await member_client.post(
        "/api/execute_query", json={"query": "SELECT 1", "db_uuid": db_uuid}
    )
    assert denied.status_code == 403
    assert denied.json()["error_code"] == "DATABASE_ACCESS_DENIED"


@pytest.mark.asyncio
async def test_revoke_leaves_the_db_admin_role_alone(async_client: AsyncClient):
    """DB ADMIN is a governance root; only the platform OWNER manages it."""
    database_id, _admin_id, member_id, admin_client = await _seed(async_client)
    app_db = app.state.context.app_db
    async with app_db.get_app_db() as db:
        db.add(
            UserDatabaseAssociation(
                user_id=member_id,
                database_id=database_id,
                role="ADMIN,WRITER",
                is_admin=True,
            )
        )
        await db.commit()

    response = await admin_client.delete(
        f"/api/admin/databases/{database_id}/users/{member_id}"
    )
    assert response.status_code == 200
    assert response.json()["remaining_role"] == "ADMIN"

    async with app_db.get_app_db() as db:
        assoc = (
            await db.execute(
                select(UserDatabaseAssociation).where(
                    UserDatabaseAssociation.user_id == member_id,
                    UserDatabaseAssociation.database_id == database_id,
                )
            )
        ).scalars().first()
        assert assoc.role == "ADMIN"
        assert assoc.is_admin is True


@pytest.mark.asyncio
async def test_revoking_an_admin_only_association_is_refused(async_client: AsyncClient):
    database_id, admin_id, _member_id, admin_client = await _seed(async_client)

    response = await admin_client.delete(
        f"/api/admin/databases/{database_id}/users/{admin_id}"
    )
    assert response.status_code == 400
    assert "OWNER" in response.text


@pytest.mark.asyncio
async def test_revoking_a_user_without_access_is_refused(async_client: AsyncClient):
    database_id, _admin_id, member_id, admin_client = await _seed(async_client)

    response = await admin_client.delete(
        f"/api/admin/databases/{database_id}/users/{member_id}"
    )
    assert response.status_code == 404
    assert response.json()["error_code"] == "DATABASE_ACCESS_NOT_FOUND"


# --- P1-9 -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_password_change_replaces_the_password(async_client: AsyncClient):
    await _register(async_client, "changer@example.com", "changer")
    client = _client(async_client)
    await _login(client, "changer@example.com")

    response = await client.post(
        "/api/me/password",
        json={"current_password": PASSWORD, "new_password": "BrandNewSecret123!"},
    )
    assert response.status_code == 200

    fresh = _client(async_client)
    assert (
        await fresh.post(
            "/api/login", json={"email": "changer@example.com", "password": PASSWORD}
        )
    ).status_code == 400
    assert (
        await fresh.post(
            "/api/login",
            json={"email": "changer@example.com", "password": "BrandNewSecret123!"},
        )
    ).status_code == 200


@pytest.mark.asyncio
async def test_password_change_requires_the_current_password(async_client: AsyncClient):
    """A stolen session must not be able to lock the real owner out."""
    await _register(async_client, "wrongcurrent@example.com", "wrongcurrent")
    client = _client(async_client)
    await _login(client, "wrongcurrent@example.com")

    response = await client.post(
        "/api/me/password",
        json={"current_password": "NotThePassword1!", "new_password": "BrandNewSecret123!"},
    )
    assert response.status_code == 400
    assert "Mevcut şifre" in response.text

    # Unchanged.
    fresh = _client(async_client)
    assert (
        await fresh.post(
            "/api/login",
            json={"email": "wrongcurrent@example.com", "password": PASSWORD},
        )
    ).status_code == 200


@pytest.mark.asyncio
async def test_password_change_enforces_the_policy(async_client: AsyncClient):
    await _register(async_client, "weak@example.com", "weakchanger")
    client = _client(async_client)
    await _login(client, "weak@example.com")

    response = await client.post(
        "/api/me/password",
        json={"current_password": PASSWORD, "new_password": "alllowercaseletters"},
    )
    assert response.status_code in (400, 422)


@pytest.mark.asyncio
async def test_password_change_rejects_reusing_the_same_password(async_client: AsyncClient):
    await _register(async_client, "same@example.com", "samechanger")
    client = _client(async_client)
    await _login(client, "same@example.com")

    response = await client.post(
        "/api/me/password",
        json={"current_password": PASSWORD, "new_password": PASSWORD},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_password_change_revokes_other_sessions_and_audits(async_client: AsyncClient):
    user_id = await _register(async_client, "multi@example.com", "multi")

    other = _client(async_client)
    await _login(other, "multi@example.com")
    current = _client(async_client)
    await _login(current, "multi@example.com")

    response = await current.post(
        "/api/me/password",
        json={"current_password": PASSWORD, "new_password": "BrandNewSecret123!"},
    )
    assert response.status_code == 200
    assert response.json()["revoked_sessions"] >= 1

    # The caller keeps working; the other session is gone.
    assert (await current.get("/api/me")).status_code == 200
    assert (await other.get("/api/me")).status_code == 401

    async with app.state.context.app_db.get_app_db() as db:
        audit = (
            await db.execute(
                select(AuditLog).where(AuditLog.action == AuditAction.PASSWORD_CHANGED)
            )
        ).scalars().all()
        assert len(audit) == 1
        assert audit[0].target_id == str(user_id)
        # No password material of any kind in the record.
        assert PASSWORD not in (audit[0].details or "")
        assert "BrandNewSecret123!" not in (audit[0].details or "")
        assert "$2b$" not in (audit[0].details or "")

        alive = (
            await db.execute(
                select(UserSession).where(
                    UserSession.user_id == user_id, UserSession.revoked_at.is_(None)
                )
            )
        ).scalars().all()
        assert len(alive) == 1


@pytest.mark.asyncio
async def test_password_change_requires_authentication(async_client: AsyncClient):
    anonymous = _client(async_client)
    response = await anonymous.post(
        "/api/me/password",
        json={"current_password": PASSWORD, "new_password": "BrandNewSecret123!"},
    )
    assert response.status_code == 401
