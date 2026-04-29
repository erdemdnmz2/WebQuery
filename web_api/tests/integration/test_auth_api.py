import pytest
import httpx
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_register_and_login(async_client: AsyncClient):
    """
    Test user registration and subsequent login.
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

@pytest.mark.asyncio
async def test_access_protected_route_without_token(async_client: AsyncClient):
    """
    Test that accessing a protected API route without a token returns 401.
    """
    response = await async_client.get("/api/workspaces")
    # Our middleware returns 401 for /api/ routes when no token is present
    assert response.status_code == 401
