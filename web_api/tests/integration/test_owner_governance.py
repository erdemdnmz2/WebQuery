"""Integration coverage for the persisted platform OWNER boundary."""

import json

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app import app
from app_database.models import AuditLog, User, UserDatabaseAssociation
from common.audit_actions import AuditAction
from owner.bootstrap import bootstrap_owner, ensure_active_owner

pytestmark = pytest.mark.asyncio


async def _register(client, username: str, email: str) -> int:
    response = await client.post(
        "/api/register",
        json={
            "username": username,
            "email": email,
            "password": "StrongPassword123!",
        },
    )
    assert response.status_code == 200, response.text
    async with app.state.context.app_db.get_app_db() as db:
        user = (
            await db.execute(select(User).where(User.email == email))
        ).scalars().one()
        return user.id


async def _login(client, email: str) -> None:
    response = await client.post(
        "/api/login",
        json={"email": email, "password": "StrongPassword123!"},
    )
    assert response.status_code == 200, response.text


async def test_bootstrap_promotes_existing_user_and_startup_guard_is_fail_closed(async_client):
    app_db = app.state.context.app_db
    with pytest.raises(SystemExit):
        await ensure_active_owner(app_db)

    existing = await _register(async_client, "bootstrap_owner", "owner@example.com")
    owner_id, changed = await bootstrap_owner(app_db, email=" OWNER@example.com ")
    assert changed is True
    assert owner_id == existing

    await ensure_active_owner(app_db)
    owner_again_id, changed_again = await bootstrap_owner(app_db, email="owner@example.com")
    assert owner_again_id == existing
    assert changed_again is False

    async with app_db.get_app_db() as db:
        audit = (
            await db.execute(
                select(AuditLog).where(AuditLog.action == AuditAction.OWNER_GRANTED)
            )
        ).scalars().one()
        assert audit.actor_username == "system:owner-bootstrap"
        assert audit.target_id == str(existing)


async def test_bootstrap_can_create_the_initial_owner(async_client):
    app_db = app.state.context.app_db
    owner_id, changed = await bootstrap_owner(
        app_db,
        email="first-owner@example.com",
        username="first_owner",
        password="StrongPassword123!",
    )
    assert changed is True

    async with app_db.get_app_db() as db:
        owner = await db.get(User, owner_id)
        assert owner is not None
        assert owner.is_active is True
        assert owner.is_platform_owner is True
        assert owner.check_password("StrongPassword123!") is True
        audit = (
            await db.execute(
                select(AuditLog).where(AuditLog.action == AuditAction.OWNER_GRANTED)
            )
        ).scalars().one()
        assert json.loads(audit.details) == {
            "source": "server_cli",
            "created_user": True,
            "activated_user": True,
        }


async def test_owner_is_not_implicitly_a_database_admin(async_client):
    owner = await _register(async_client, "owner_only", "owner-only@example.com")
    async with app.state.context.app_db.get_app_db() as db, db.begin():
        persisted = await db.get(User, owner)
        persisted.is_platform_owner = True
    await _login(async_client, "owner-only@example.com")

    assert (await async_client.get("/api/owner/users")).status_code == 200
    profile = await async_client.get("/api/me")
    assert profile.json()["is_platform_owner"] is True
    assert profile.json()["is_admin"] is False
    assert (await async_client.get("/api/admin/queries_to_approve")).status_code == 403


async def test_database_admin_grant_and_last_admin_guard(async_client):
    owner = await _register(async_client, "governance_owner", "governance-owner@example.com")
    first_admin = await _register(async_client, "first_db_admin", "first-admin@example.com")
    second_admin = await _register(async_client, "second_db_admin", "second-admin@example.com")
    inactive_admin = await _register(async_client, "inactive_db_admin", "inactive-admin@example.com")
    async with app.state.context.app_db.get_app_db() as db, db.begin():
        persisted = await db.get(User, owner)
        persisted.is_platform_owner = True
        inactive = await db.get(User, inactive_admin)
        inactive.is_active = False
    await _login(async_client, "governance-owner@example.com")

    rejected_database = await async_client.post(
        "/api/owner/databases",
        json={
            "servername": "rejected-server",
            "database_name": "rejected-db",
            "tech_name": "postgresql",
            "connection_mode": "ro",
            "initial_admin_user_id": inactive_admin,
            "username_ro": "rejected_ro",
            "password_ro": "test-credential",
        },
    )
    assert rejected_database.status_code == 400
    assert rejected_database.json()["error_code"] == "DATABASE_ADMIN_INACTIVE"
    assert all(
        item["database_name"] != "rejected-db"
        for item in (await async_client.get("/api/owner/databases")).json()
    )

    created = await async_client.post(
        "/api/owner/databases",
        json={
            "servername": "governance-server",
            "database_name": "governance-db",
            "tech_name": "postgresql",
            "connection_mode": "ro",
            "initial_admin_user_id": first_admin,
            "username_ro": "governance_ro",
            "password_ro": "test-credential",
        },
    )
    assert created.status_code == 201, created.text
    databases = (await async_client.get("/api/owner/databases")).json()
    database_id = next(item["id"] for item in databases if item["database_name"] == "governance-db")

    async with AsyncClient(
        transport=async_client._transport, base_url="http://test"
    ) as db_admin_client:
        await _login(db_admin_client, "first-admin@example.com")
        forbidden_grant = await db_admin_client.post(
            "/api/admin/associate_user",
            json={
                "user_id": second_admin,
                "database_id": database_id,
                "role": "ADMIN",
            },
        )
        assert forbidden_grant.status_code == 400
        assert forbidden_grant.json()["error_code"] == "DATABASE_ADMIN_OWNER_REQUIRED"

        data_role_change = await db_admin_client.post(
            "/api/admin/associate_user",
            json={
                "user_id": first_admin,
                "database_id": database_id,
                "role": "READER",
            },
        )
        assert data_role_change.status_code == 200, data_role_change.text

    last_revoke = await async_client.delete(
        f"/api/owner/databases/{database_id}/admins/{first_admin}"
    )
    assert last_revoke.status_code == 409
    assert last_revoke.json()["error_code"] == "LAST_DATABASE_ADMIN"

    inactive_grant = await async_client.post(
        f"/api/owner/databases/{database_id}/admins/{inactive_admin}"
    )
    assert inactive_grant.status_code == 400
    assert inactive_grant.json()["error_code"] == "DATABASE_ADMIN_INACTIVE"

    granted = await async_client.post(
        f"/api/owner/databases/{database_id}/admins/{second_admin}"
    )
    assert granted.status_code == 200, granted.text
    revoked = await async_client.delete(
        f"/api/owner/databases/{database_id}/admins/{first_admin}"
    )
    assert revoked.status_code == 200, revoked.text

    async with app.state.context.app_db.get_app_db() as db:
        associations = (
            await db.execute(
                select(UserDatabaseAssociation).where(
                    UserDatabaseAssociation.database_id == database_id
                )
            )
        ).scalars().all()
        assert sorted((item.user_id, item.role) for item in associations) == sorted(
            [(first_admin, "READER"), (second_admin, "ADMIN")]
        )
