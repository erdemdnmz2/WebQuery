"""
Integration tests for User Authentication, Registration, and Session management.
Includes rate limiting bypass, password policy validations, JWT cookie handling,
and session invalidation upon logout.
"""
import hashlib

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app import app
from app_database.models import AuditLog, User, UserSession
from common.audit_actions import AuditAction


@pytest.mark.asyncio
async def test_register_and_login(async_client: AsyncClient):
    """
    Test successful user registration and subsequent login setting cookies.
    """
    # 1. Register a new user
    register_data = {
        "username": "testuser",
        "email": "test@example.com",
        "password": "StrongPassword123!"
    }
    
    response = await async_client.post("/api/register", json=register_data)
    assert response.status_code == 200, f"Registration failed: {response.text}"
    
    data = response.json()
    assert data["success"] is True
    
    # 2. Login with the created user
    login_data = {
        "email": "test@example.com",
        "password": "StrongPassword123!"
    }
    
    response = await async_client.post("/api/login", json=login_data)
    assert response.status_code == 200, f"Login failed: {response.text}"
    
    assert response.json() == {"ok": True}

    # Tokens are cookie-only: JavaScript must not receive an access JWT in JSON.
    assert "access_token" in response.cookies
    assert "refresh_token" in response.cookies
    set_cookies = response.headers.get_list("set-cookie")
    assert any(
        header.startswith("refresh_token=") and "Path=/api/refresh" in header
        for header in set_cookies
    )

    async with app.state.context.app_db.get_app_db() as db:
        session = (
            await db.execute(
                select(UserSession)
                .join(User, UserSession.user_id == User.id)
                .where(User.email == login_data["email"])
            )
        ).scalars().one()
        refresh_token = response.cookies["refresh_token"]
        assert session.refresh_hash == hashlib.sha256(refresh_token.encode("utf-8")).hexdigest()
        assert session.refresh_hash != refresh_token

        audits = (
            await db.execute(
                select(AuditLog).where(
                    AuditLog.action.in_(
                        [AuditAction.USER_REGISTERED, AuditAction.LOGIN]
                    )
                )
            )
        ).scalars().all()
        assert {row.action for row in audits} == {
            AuditAction.USER_REGISTERED,
            AuditAction.LOGIN,
        }
        assert all(row.client_ip == "127.0.0.1" for row in audits)


@pytest.mark.asyncio
async def test_login_invalid_credentials(async_client: AsyncClient):
    """
    Test login failures with non-existent user and incorrect password.
    """
    # 1. Login with unregistered user
    login_data = {
        "email": "nonexistent@example.com",
        "password": "StrongPassword123!"
    }
    response = await async_client.post("/api/login", json=login_data)
    assert response.status_code == 400
    assert "Invalid email or password" in response.text

    # 2. Register a user
    register_data = {
        "username": "auth_user",
        "email": "auth_user@example.com",
        "password": "StrongPassword123!"
    }
    response = await async_client.post("/api/register", json=register_data)
    assert response.status_code == 200

    # 3. Login with incorrect password
    bad_login_data = {
        "email": "auth_user@example.com",
        "password": "WrongPassword999!"
    }
    response = await async_client.post("/api/login", json=bad_login_data)
    assert response.status_code == 400
    assert "Invalid email or password" in response.text

    async with app.state.context.app_db.get_app_db() as db:
        failed_audits = (
            await db.execute(
                select(AuditLog).where(AuditLog.action == AuditAction.LOGIN_FAILED)
            )
        ).scalars().all()
        assert len(failed_audits) == 2
        assert all(row.client_ip == "127.0.0.1" for row in failed_audits)


@pytest.mark.asyncio
async def test_register_duplicate_email(async_client: AsyncClient):
    """
    Test that registering an email already in use yields a 400 bad request.
    """
    register_data = {
        "username": "dup_user1",
        "email": "duplicate@example.com",
        "password": "StrongPassword123!"
    }
    
    response = await async_client.post("/api/register", json=register_data)
    assert response.status_code == 200

    # Attempt second registration with same email
    register_data_2 = {
        "username": "dup_user2",
        "email": "duplicate@example.com",
        "password": "DifferentPassword123!"
    }
    response = await async_client.post("/api/register", json=register_data_2)
    assert response.status_code == 400
    data = response.json()
    assert data["error_code"] == "USER_ALREADY_EXISTS"
    assert "Email already registered" in data["message"]


@pytest.mark.asyncio
async def test_register_invalid_password(async_client: AsyncClient):
    """
    Test that registration rejects passwords violating the security policy.
    """
    # 1. Short password
    register_data = {
        "username": "weak_user1",
        "email": "weak1@example.com",
        "password": "Short1!"
    }
    response = await async_client.post("/api/register", json=register_data)
    assert response.status_code == 400
    assert "Şifre en az 12 karakter olmalıdır" in response.json()["detail"]

    # 2. No uppercase or numbers
    register_data_2 = {
        "username": "weak_user2",
        "email": "weak2@example.com",
        "password": "lowercaseonly!"
    }
    response = await async_client.post("/api/register", json=register_data_2)
    assert response.status_code == 400
    assert "Şifre en az bir büyük harf ve bir rakam içermelidir" in response.json()["detail"]


@pytest.mark.asyncio
async def test_access_protected_route_without_token(async_client: AsyncClient):
    """
    Test that accessing protected endpoints without access_token cookie returns 401.
    """
    response = await async_client.get("/api/workspaces")
    assert response.status_code == 401
    assert "Token required" in response.text


@pytest.mark.asyncio
async def test_access_me_protected_route(async_client: AsyncClient):
    """
    Test that logged in user can successfully retrieve their profile via /api/me.
    """
    # 1. Register and login
    register_data = {
        "username": "profile_user",
        "email": "profile@example.com",
        "password": "StrongPassword123!"
    }
    await async_client.post("/api/register", json=register_data)
    
    login_data = {
        "email": "profile@example.com",
        "password": "StrongPassword123!"
    }
    await async_client.post("/api/login", json=login_data)

    # 2. Retrieve user details
    response = await async_client.get("/api/me")
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "profile_user"
    assert data["is_admin"] is False


@pytest.mark.asyncio
async def test_access_me_invalid_token(async_client: AsyncClient):
    """
    Test that profile retrieval returns 401 when access_token cookie is corrupted/invalid.
    """
    async_client.cookies.set("access_token", "invalid_jwt_token_format_xxxx")
    response = await async_client.get("/api/me")
    assert response.status_code == 401
    assert "Invalid token" in response.json()["detail"]


@pytest.mark.asyncio
async def test_logout_flow(async_client: AsyncClient):
    """
    Test complete logout flow: clears cookies and writes the logout audit record.
    """
    # 1. Register and login
    register_data = {
        "username": "logout_user",
        "email": "logout@example.com",
        "password": "StrongPassword123!"
    }
    await async_client.post("/api/register", json=register_data)
    
    login_data = {
        "email": "logout@example.com",
        "password": "StrongPassword123!"
    }
    await async_client.post("/api/login", json=login_data)

    # Verify cookies contain token
    assert "access_token" in async_client.cookies

    # 2. Perform logout
    response = await async_client.post("/api/logout")
    assert response.status_code == 200
    assert "Successfully logged out" in response.json()["message"]

    # 3. Verify cookie was deleted
    # Note: In HTTP clients, deleting a cookie sets it to empty or expires it immediately
    assert "access_token" not in async_client.cookies or async_client.cookies.get("access_token") == ""

    async with app.state.context.app_db.get_app_db() as db:
        logout_audit = (
            await db.execute(
                select(AuditLog).where(AuditLog.action == AuditAction.LOGOUT)
            )
        ).scalar_one()
        assert logout_audit.client_ip == "127.0.0.1"


@pytest.mark.asyncio
async def test_refresh_rotates_tokens_and_logout_revokes_session(async_client: AsyncClient):
    register_data = {
        "username": "refresh_user",
        "email": "refresh@example.com",
        "password": "StrongPassword123!",
    }
    await async_client.post("/api/register", json=register_data)
    login = await async_client.post(
        "/api/login",
        json={"email": register_data["email"], "password": register_data["password"]},
    )
    assert login.status_code == 200
    assert "refresh_token" in async_client.cookies
    old_refresh = async_client.cookies["refresh_token"]

    refreshed = await async_client.post("/api/refresh")
    assert refreshed.status_code == 200
    assert "refresh_token" in async_client.cookies
    assert async_client.cookies["refresh_token"] != old_refresh
    assert any(
        header.startswith("refresh_token=") and "Path=/api/refresh" in header
        for header in refreshed.headers.get_list("set-cookie")
    )

    logout = await async_client.post("/api/logout")
    assert logout.status_code == 200

    protected = await async_client.get("/api/me")
    assert protected.status_code == 401
