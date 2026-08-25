"""Integration tests for admin user disablement and request-time enforcement."""

from contextlib import asynccontextmanager

import pytest
from httpx import ASGITransport, AsyncClient
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


async def _register_and_login(
    client: AsyncClient,
    *,
    username: str,
    email: str,
    password: str = "StrongPassword123!",
) -> None:
    registered = await client.post(
        "/api/register",
        json={"username": username, "email": email, "password": password},
    )
    assert registered.status_code == 200, registered.text

    logged_in = await client.post(
        "/api/login",
        json={"email": email, "password": password},
    )
    assert logged_in.status_code == 200, logged_in.text


@asynccontextmanager
async def _client_from_transport(transport: ASGITransport):
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def _make_admin(client: AsyncClient, *, suffix: str) -> int:
    await _register_and_login(
        client,
        username=f"admin_{suffix}",
        email=f"admin_{suffix}@example.com",
    )
    async with app.state.context.app_db.get_app_db() as db:
        admin = (
            await db.execute(
                select(User).where(User.email == f"admin_{suffix}@example.com")
            )
        ).scalars().one()
        database = Databases(
            servername=f"server_{suffix}",
            database_name=f"database_{suffix}",
            technology="sqlite",
        )
        db.add(database)
        await db.flush()
        db.add(
            UserDatabaseAssociation(
                user_id=admin.id,
                database_id=database.id,
                role="ADMIN",
                is_admin=True,
            )
        )
        admin_id = admin.id
        await db.commit()
        return admin_id


@pytest.mark.asyncio
async def test_admin_disable_revokes_sessions_and_blocks_existing_tokens(async_client):
    transport = async_client._transport
    async with (
        _client_from_transport(transport) as target_client,
        _client_from_transport(transport) as admin_client,
    ):
        await _register_and_login(
            target_client,
            username="disable_target",
            email="disable_target@example.com",
        )
        admin_id = await _make_admin(admin_client, suffix="disable")

        async with app.state.context.app_db.get_app_db() as db:
            target = (
                await db.execute(
                    select(User).where(User.email == "disable_target@example.com")
                )
            ).scalars().one()
            target_id = target.id
            session_count = (
                await db.execute(
                    select(UserSession).where(
                        UserSession.user_id == target_id,
                        UserSession.revoked_at.is_(None),
                    )
                )
            ).scalars().all()
            assert len(session_count) == 1

        response = await admin_client.post(f"/api/admin/users/{target_id}/disable")
        assert response.status_code == 200, response.text
        assert response.json() == {
            "success": True,
            "message": "User disabled successfully",
        }

        # The middleware blocks the already-issued access token before the
        # endpoint dependency runs.
        protected = await target_client.get("/api/me")
        assert protected.status_code == 401
        assert protected.json()["detail"] == "Invalid token"

        # Refresh is intentionally middleware-exempt, so its own active check
        # must also reject the disabled account.
        refreshed = await target_client.post("/api/refresh")
        assert refreshed.status_code == 401

        # Login must reject the disabled account without revealing account state.
        login_client = AsyncClient(transport=transport, base_url="http://test")
        try:
            login = await login_client.post(
                "/api/login",
                json={
                    "email": "disable_target@example.com",
                    "password": "StrongPassword123!",
                },
            )
        finally:
            await login_client.aclose()
        assert login.status_code == 400
        assert login.json()["detail"] == "Invalid email or password"

    async with app.state.context.app_db.get_app_db() as db:
        target = (
            await db.execute(
                select(User).where(User.email == "disable_target@example.com")
            )
        ).scalars().one()
        assert target.is_active is False
        assert target.disabled_by == "admin_disable"
        sessions = (
            await db.execute(select(UserSession).where(UserSession.user_id == target.id))
        ).scalars().all()
        assert sessions and all(session.revoked_at is not None for session in sessions)
        audit = (
            await db.execute(
                select(AuditLog).where(
                    AuditLog.action == AuditAction.USER_DISABLED,
                    AuditLog.target_id == str(target.id),
                )
            )
        ).scalars().one()
        assert audit.actor_user_id == admin_id
        assert audit.actor_username == "admin_disable"
        assert audit.client_ip == "127.0.0.1"


@pytest.mark.asyncio
async def test_disable_rejects_self_and_non_admin(async_client):
    transport = async_client._transport
    async with (
        _client_from_transport(transport) as admin_client,
        _client_from_transport(transport) as regular_client,
    ):
        admin_id = await _make_admin(admin_client, suffix="rules")
        await _register_and_login(
            regular_client,
            username="regular_rules",
            email="regular_rules@example.com",
        )

        self_disable = await admin_client.post(f"/api/admin/users/{admin_id}/disable")
        assert self_disable.status_code == 400
        assert self_disable.json()["error_code"] == "CANNOT_DISABLE_SELF"

        async with app.state.context.app_db.get_app_db() as db:
            regular = (
                await db.execute(
                    select(User).where(User.email == "regular_rules@example.com")
                )
            ).scalars().one()
            regular_id = regular.id

        forbidden = await regular_client.post(f"/api/admin/users/{regular_id}/disable")
        assert forbidden.status_code == 403

        missing = await admin_client.post("/api/admin/users/999999/disable")
        assert missing.status_code == 404
