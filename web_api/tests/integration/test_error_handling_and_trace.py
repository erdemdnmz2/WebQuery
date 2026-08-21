"""
Centralized Exception Handling and Trace ID tracking integration tests.
Verifies Trace ID headers, global exception routing, and error translation.
"""
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app import app
from app_database.models import Databases, User, UserDatabaseAssociation


@pytest.fixture
def mock_db_session():
    """
    Fixture that patches DatabaseProvider.get_session to return a mock session.
    """
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_session.execute.return_value = mock_result
    
    @asynccontextmanager
    async def fake_get_session(user, db_uuid):
        yield mock_session
        
    with patch("database_provider.DatabaseProvider.get_session", side_effect=fake_get_session):
        yield mock_session, mock_result

@pytest.mark.asyncio
async def test_trace_id_header_on_public_route(async_client: AsyncClient):
    """
    Test that even public endpoints (like /health) return the X-Request-ID trace header.
    """
    response = await async_client.get("/health")
    assert response.status_code == 200
    assert "X-Request-ID" in response.headers
    assert len(response.headers["X-Request-ID"]) > 0

@pytest.mark.asyncio
async def test_query_execution_error_translation(async_client: AsyncClient, mock_db_session):
    """
    Test that database execution exceptions are wrapped into QueryExecutionError,
    caught by the global handler, and returned as a clean 400 Bad Request.
    """
    mock_session, mock_result = mock_db_session
    
    # 1. Inject mock database
    app_db = app.state.context.app_db
    db_uuid = None
    db_id = None
    async with app_db.get_app_db() as db:
        test_db = Databases(
            servername="trace-server",
            database_name="trace-db",
            technology="postgresql"
        )
        db.add(test_db)
        await db.commit()
        await db.refresh(test_db)
        db_uuid = test_db.uuid
        db_id = test_db.id
    
    # Reload db_info in provider
    db_info = await app_db.get_db_info()
    app.state.context.db_provider.set_db_info(db_info)
    
    # 2. Register and login
    register_data = {
        "username": "traceuser",
        "email": "trace@example.com",
        "password": "StrongPassword123!"
    }
    await async_client.post("/api/register", json=register_data)
    
    login_data = {
        "email": "trace@example.com",
        "password": "StrongPassword123!"
    }
    await async_client.post("/api/login", json=login_data)

    # Setup UserDatabaseAssociation
    async with app_db.get_app_db() as db:
        user_res = await db.execute(select(User).where(User.email == "trace@example.com"))
        test_user = user_res.scalars().first()
        assoc = UserDatabaseAssociation(
            user_id=test_user.id,
            database_id=db_id,
            role="READER",
            is_admin=False
        )
        db.add(assoc)
        await db.commit()
    
    # 3. Configure mock session to raise a database execution exception (e.g. syntax error)
    mock_session.execute.side_effect = Exception("column 'non_existent' does not exist")
    
    # 4. Execute query
    query_payload = {
        "query": "SELECT non_existent FROM users",
        "db_uuid": db_uuid
    }
    response = await async_client.post("/api/execute_query", json=query_payload)
    
    # Assert REST status is 400 (Bad Request) instead of 500 or 200 with error
    assert response.status_code == 400
    
    resp_data = response.json()
    assert resp_data["success"] is False
    assert resp_data["error_code"] == "QUERY_EXECUTION_FAILED"
    assert "column 'non_existent' does not exist" in resp_data["message"]
    assert "column 'non_existent' does not exist" in resp_data["error"]
    
    # Verify Trace ID matches the response header
    assert "X-Request-ID" in response.headers
    assert resp_data["trace_id"] == response.headers["X-Request-ID"]

@pytest.mark.asyncio
async def test_workspace_not_found_error_translation(async_client: AsyncClient):
    """
    Test that attempting to access a non-existent workspace raises WorkspaceNotFoundError
    which is translated by the global handler into a clean 404 Not Found.
    """
    # 1. Register and login
    register_data = {
        "username": "traceuser2",
        "email": "trace2@example.com",
        "password": "StrongPassword123!"
    }
    await async_client.post("/api/register", json=register_data)
    
    login_data = {
        "email": "trace2@example.com",
        "password": "StrongPassword123!"
    }
    await async_client.post("/api/login", json=login_data)
    
    # 2. Get non-existent workspace (ID: 99999)
    response = await async_client.get("/api/get_workspace_by_id/99999")
    
    # Assert REST status is 404 (Not Found) instead of 400 or 500
    assert response.status_code == 404
    
    resp_data = response.json()
    assert resp_data["success"] is False
    assert resp_data["error_code"] == "WORKSPACE_NOT_FOUND"
    assert "Workspace not found" in resp_data["message"]
    
    # Verify Trace ID matches header
    assert "X-Request-ID" in response.headers
    assert resp_data["trace_id"] == response.headers["X-Request-ID"]
