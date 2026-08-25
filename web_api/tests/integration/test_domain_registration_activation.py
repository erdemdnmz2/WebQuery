"""Domain allowlist registration and platform-scoped activation tests."""

import pytest
from sqlalchemy import select

from app import app
from app_database.models import AuditLog, Databases, User, UserDatabaseAssociation
from authentication import config as auth_config
from common.audit_actions import AuditAction

pytestmark = pytest.mark.asyncio


async def _create_active_user(username: str, email: str) -> User:
    async with app.state.context.app_db.get_app_db() as db, db.begin():
        user = User(username=username, email=email, is_active=True)
        user.set_password("StrongPassword123!")
        db.add(user)
        await db.flush()
        return user


async def _user_by_email(email: str) -> User:
    async with app.state.context.app_db.get_app_db() as db:
        return (
            await db.execute(select(User).where(User.email == email))
        ).scalars().one()


async def test_registration_is_domain_scoped_and_pending(async_client, monkeypatch):
    monkeypatch.setattr(auth_config, "ALLOWED_EMAIL_DOMAINS", ("company.com",))
    monkeypatch.setattr(auth_config, "REGISTRATION_REQUIRES_ACTIVATION", True)

    rejected = await async_client.post(
        "/api/register",
        json={
            "username": "outside",
            "email": "outside@example.com",
            "password": "StrongPassword123!",
        },
    )
    assert rejected.status_code == 403
    async with app.state.context.app_db.get_app_db() as db:
        assert (
            await db.execute(select(User).where(User.email == "outside@example.com"))
        ).scalars().first() is None

    registered = await async_client.post(
        "/api/register",
        json={
            "username": "pending_user",
            "email": "pending@company.com",
            "password": "StrongPassword123!",
        },
    )
    assert registered.status_code == 200, registered.text
    assert "etkinleştirdiğinde" in registered.json()["message"]

    pending = await _user_by_email("pending@company.com")
    assert pending.is_active is False
    login = await async_client.post(
        "/api/login",
        json={"email": "pending@company.com", "password": "StrongPassword123!"},
    )
    assert login.status_code == 400


async def test_platform_admin_lists_and_enables_pending_user(async_client, monkeypatch):
    monkeypatch.setattr(auth_config, "ALLOWED_EMAIL_DOMAINS", ("company.com",))
    monkeypatch.setattr(auth_config, "REGISTRATION_REQUIRES_ACTIVATION", True)
    monkeypatch.setenv("PLATFORM_ADMINS", "platform_admin")

    await _create_active_user("platform_admin", "platform_admin@company.com")
    admin_login = await async_client.post(
        "/api/login",
        json={"email": "platform_admin@company.com", "password": "StrongPassword123!"},
    )
    assert admin_login.status_code == 200

    registered = await async_client.post(
        "/api/register",
        json={
            "username": "employee",
            "email": "employee@company.com",
            "password": "StrongPassword123!",
        },
    )
    assert registered.status_code == 200
    pending = await _user_by_email("employee@company.com")

    users = await async_client.get("/api/admin/users")
    assert users.status_code == 200, users.text
    listed = next(item for item in users.json() if item["id"] == pending.id)
    assert listed["status"] == "pending"

    enabled = await async_client.post(f"/api/admin/users/{pending.id}/enable")
    assert enabled.status_code == 200, enabled.text

    active = await _user_by_email("employee@company.com")
    assert active.is_active is True
    async with app.state.context.app_db.get_app_db() as db:
        audit = (
            await db.execute(
                select(AuditLog).where(
                    AuditLog.action == AuditAction.USER_ENABLED,
                    AuditLog.target_id == str(pending.id),
                )
            )
        ).scalars().one()
        assert audit.actor_username == "platform_admin"


async def test_database_admin_is_not_platform_admin(async_client, monkeypatch):
    monkeypatch.setenv("PLATFORM_ADMINS", "someone_else")
    await _create_active_user("database_admin", "database_admin@company.com")
    async with app.state.context.app_db.get_app_db() as db, db.begin():
        user_id = (
            await db.execute(
                select(User).where(User.email == "database_admin@company.com")
            )
        ).scalars().one().id
        database = Databases(
            servername="db-admin-server",
            database_name="db-admin-database",
            technology="sqlite",
        )
        db.add(database)
        await db.flush()
        db.add(
            UserDatabaseAssociation(
                user_id=user_id,
                database_id=database.id,
                role="ADMIN",
                is_admin=True,
            )
        )
    # A database ADMIN must not be promoted to platform scope by association.
    await async_client.post(
        "/api/login",
        json={"email": "database_admin@company.com", "password": "StrongPassword123!"},
    )
    response = await async_client.get("/api/admin/users")
    assert response.status_code == 403
