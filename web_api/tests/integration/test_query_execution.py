"""
Integration tests for query execution endpoints.
Verifies SELECT and DML/non-SELECT query execution paths and safety.
"""
import pytest
from httpx import AsyncClient
from unittest.mock import MagicMock, AsyncMock, patch
from contextlib import asynccontextmanager

from app import app
from app_database.models import Databases

@pytest.fixture
def mock_db_session():
    """
    Fixture that patches DatabaseProvider.get_session to return a mock session.
    """
    mock_session = AsyncMock()
    mock_result = MagicMock()
    
    # We will configure the mock_result inside each test case
    mock_session.execute.return_value = mock_result
    
    @asynccontextmanager
    async def fake_get_session(user, servername, database_name):
        yield mock_session
        
    with patch("database_provider.DatabaseProvider.get_session", side_effect=fake_get_session):
        yield mock_session, mock_result

@pytest.mark.asyncio
async def test_select_query_execution(async_client: AsyncClient, mock_db_session):
    """
    Test that a SELECT query returns data successfully.
    """
    mock_session, mock_result = mock_db_session
    
    # 1. Setup mock database in metadata DB
    app_db = app.state.app_db
    async with app_db.get_app_db() as db:
        # Add a test database entry to Databases table
        test_db = Databases(
            servername="test-server",
            database_name="test-db",
            technology="postgresql"
        )
        db.add(test_db)
        await db.commit()
        
    # Reload db_info in db_provider to pick up the new database
    db_info = await app_db.get_db_info()
    app.state.db_provider.set_db_info(db_info)
    
    # 2. Register and login
    register_data = {
        "username": "queryuser",
        "email": "query@example.com",
        "password": "StrongPassword123!"
    }
    await async_client.post("/api/register", json=register_data)
    
    login_data = {
        "email": "query@example.com",
        "password": "StrongPassword123!"
    }
    await async_client.post("/api/login", json=login_data)
    
    # 3. Configure mock result for SELECT (returns rows)
    mock_result.returns_rows = True
    
    # Create a mock row with a _mapping dictionary
    mock_row = MagicMock()
    mock_row._mapping = {"id": 1, "name": "John Doe"}
    mock_result.fetchmany.return_value = [mock_row]
    
    # 4. Execute the query via API
    query_payload = {
        "query": "SELECT * FROM users",
        "servername": "test-server",
        "database_name": "test-db"
    }
    response = await async_client.post("/api/execute_query", json=query_payload)
    assert response.status_code == 200, f"Query execution failed: {response.text}"
    
    resp_data = response.json()
    assert resp_data["response_type"] == "data"
    assert resp_data["data"] == [{"id": 1, "name": "John Doe"}]
    assert "1 rows returned" in resp_data["message"]

@pytest.mark.asyncio
async def test_dml_query_execution(async_client: AsyncClient, mock_db_session):
    """
    Test that a DML/non-SELECT query (like UPDATE) returns affected rows count successfully
    and does not crash with ResourceClosedError.
    """
    mock_session, mock_result = mock_db_session
    
    # Register and login
    register_data = {
        "username": "queryuser2",
        "email": "query2@example.com",
        "password": "StrongPassword123!"
    }
    await async_client.post("/api/register", json=register_data)
    
    login_data = {
        "email": "query2@example.com",
        "password": "StrongPassword123!"
    }
    await async_client.post("/api/login", json=login_data)
    
    # Configure mock result for UPDATE (does NOT return rows)
    mock_result.returns_rows = False
    mock_result.rowcount = 3
    
    # Execute the query via API
    query_payload = {
        "query": "UPDATE users SET active = 1 WHERE age > 30",
        "servername": "test-server",
        "database_name": "test-db"
    }
    response = await async_client.post("/api/execute_query", json=query_payload)
    assert response.status_code == 200, f"Query execution failed: {response.text}"
    
    resp_data = response.json()
    assert resp_data["response_type"] == "data"
    assert resp_data["data"] == []
    assert resp_data["message"] == "3 rows affected"
