"""
Integration tests for User Authentication, Registration, and Session management.
Includes rate limiting bypass, password policy validations, JWT cookie handling,
and clean engine shutdowns upon logout.
"""
import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient
from app import app

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
    
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    
    # Verify cookie is set in response headers
    assert "access_token" in response.cookies
    cookie = response.cookies["access_token"]
    assert cookie is not None


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
    Test complete logout flow: clears cookie, logs session update, and closes user DB engines.
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

    # 2. Mock db_provider.close_user_engines
    db_provider = app.state.db_provider
    with patch.object(db_provider, "close_user_engines", new_callable=AsyncMock) as mock_close:
        # 3. Perform logout
        response = await async_client.post("/api/logout")
        assert response.status_code == 200
        assert "Successfully logged out" in response.json()["message"]

        # 4. Verify cookie was deleted
        # Note: In HTTP clients, deleting a cookie sets it to empty or expires it immediately
        assert "access_token" not in async_client.cookies or async_client.cookies.get("access_token") == ""

        # 5. Verify close_user_engines was called
        mock_close.assert_called_once()
        called_user_id = mock_close.call_args[0][0]
        assert isinstance(called_user_id, int)
