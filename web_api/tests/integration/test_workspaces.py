"""
Integration tests for workspaces router and service layer.
Verifies Workspace CRUD operations, ownership validation, and execution rules.
"""
import pytest
from httpx import AsyncClient
from unittest.mock import MagicMock, AsyncMock, patch
from contextlib import asynccontextmanager

from app import app
from app_database.models import Workspace, QueryData

@pytest.fixture
def mock_db_session():
    """
    Fixture that patches DatabaseProvider.get_session to return a mock session.
    """
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_session.execute.return_value = mock_result
    
    @asynccontextmanager
    async def fake_get_session(user, servername, database_name):
        yield mock_session
        
    with patch("database_provider.DatabaseProvider.get_session", side_effect=fake_get_session):
        yield mock_session, mock_result


async def create_user_and_login(async_client: AsyncClient, email: str, username: str) -> None:
    """
    Helper function to register and login a user.
    """
    register_data = {
        "username": username,
        "email": email,
        "password": "StrongPassword123!"
    }
    await async_client.post("/api/register", json=register_data)
    
    login_data = {
        "email": email,
        "password": "StrongPassword123!"
    }
    await async_client.post("/api/login", json=login_data)


@pytest.mark.asyncio
async def test_workspace_crud_operations(async_client: AsyncClient):
    """
    Tests creating, listing, updating, retrieving, and deleting workspaces.
    """
    # 1. Register and login
    await create_user_and_login(async_client, "user1@example.com", "user1")
    
    # 2. Create workspace
    create_payload = {
        "name": "My Workspace",
        "query": "SELECT * FROM my_table",
        "servername": "localhost",
        "database_name": "my_db"
    }
    create_response = await async_client.post("/api/workspaces", json=create_payload)
    assert create_response.status_code == 200, f"Failed to create workspace: {create_response.text}"
    create_data = create_response.json()
    assert create_data["success"] is True
    workspace_id = create_data["workspace_id"]
    
    # 3. Get workspace details
    detail_response = await async_client.get(f"/api/get_workspace_by_id/{workspace_id}")
    assert detail_response.status_code == 200
    detail_data = detail_response.json()
    assert detail_data["name"] == "My Workspace"
    assert detail_data["query"] == "SELECT * FROM my_table"
    assert detail_data["servername"] == "localhost"
    assert detail_data["database_name"] == "my_db"
    assert detail_data["status"] == "saved_in_workspace"  # Newly created queries default to saved_in_workspace
    
    # 4. List workspaces
    list_response = await async_client.get("/api/workspaces")
    assert list_response.status_code == 200
    list_data = list_response.json()
    assert len(list_data["workspaces"]) == 1
    assert list_data["workspaces"][0]["id"] == workspace_id
    
    # 5. Update workspace query
    update_payload = {
        "query": "SELECT count(*) FROM my_table",
        "status": "saved_in_workspace"
    }
    update_response = await async_client.put(f"/api/workspaces/{workspace_id}", json=update_payload)
    assert update_response.status_code == 200
    
    # Verify update
    detail_response_2 = await async_client.get(f"/api/get_workspace_by_id/{workspace_id}")
    detail_data_2 = detail_response_2.json()
    assert detail_data_2["query"] == "SELECT count(*) FROM my_table"
    
    # 6. Delete workspace
    delete_response = await async_client.delete(f"/api/workspaces/{workspace_id}")
    assert delete_response.status_code == 200
    
    # Verify deletion
    list_response_2 = await async_client.get("/api/workspaces")
    assert len(list_response_2.json()["workspaces"]) == 0


@pytest.mark.asyncio
async def test_workspace_ownership_access_controls(async_client: AsyncClient):
    """
    Tests that a user cannot access, modify, or delete workspaces owned by another user.
    """
    # 1. Login user1 and create a workspace
    await create_user_and_login(async_client, "owner@example.com", "owner")
    create_payload = {
        "name": "Owner Workspace",
        "query": "SELECT 1",
        "servername": "localhost",
        "database_name": "db"
    }
    create_response = await async_client.post("/api/workspaces", json=create_payload)
    workspace_id = create_response.json()["workspace_id"]
    
    # 2. Login user2 (attacker)
    await create_user_and_login(async_client, "attacker@example.com", "attacker")
    
    # 3. Attacker tries to get details -> should fail
    get_response = await async_client.get(f"/api/get_workspace_by_id/{workspace_id}")
    assert get_response.status_code == 403
    assert get_response.json()["error_code"] == "WORKSPACE_ACCESS_DENIED"
    
    # 4. Attacker tries to update -> should fail
    update_payload = {
        "query": "DROP TABLE users",
        "status": "saved_in_workspace"
    }
    update_response = await async_client.put(f"/api/workspaces/{workspace_id}", json=update_payload)
    assert update_response.status_code == 403
    assert update_response.json()["error_code"] == "WORKSPACE_ACCESS_DENIED"
    
    # 5. Attacker tries to delete -> should fail
    delete_response = await async_client.delete(f"/api/workspaces/{workspace_id}")
    assert delete_response.status_code == 403
    assert delete_response.json()["error_code"] == "WORKSPACE_ACCESS_DENIED"


@pytest.mark.asyncio
async def test_workspace_execution_rules(async_client: AsyncClient, mock_db_session):
    """
    Tests query execution workflows on a workspace.
    A workspace query must be approved and show_results must be True to execute.
    """
    mock_session, mock_result = mock_db_session
    
    # 1. Login and create workspace
    await create_user_and_login(async_client, "exec@example.com", "exec_user")
    create_payload = {
        "name": "Execution Workspace",
        "query": "SELECT * FROM orders",
        "servername": "localhost",
        "database_name": "sales_db"
    }
    create_response = await async_client.post("/api/workspaces", json=create_payload)
    workspace_id = create_response.json()["workspace_id"]
    
    # 2. Try to execute immediately (default is saved_in_workspace/unapproved) -> should fail with 400 Bad Request
    exec_response = await async_client.post(f"/api/execute_workspace/{workspace_id}")
    assert exec_response.status_code == 400
    assert exec_response.json()["error_code"] == "QUERY_REJECTED_BY_ANALYZER"
    
    # 3. Manually approve workspace with show_results=True in metadata DB
    app_db = app.state.app_db
    async with app_db.get_app_db() as db:
        ws = await db.get(Workspace, workspace_id)
        ws.show_results = True
        
        query_data = await db.get(QueryData, ws.query_id)
        query_data.status = "approved_with_results"
        await db.commit()
        
    # 4. Configure mock result for SELECT query
    mock_result.returns_rows = True
    mock_row = MagicMock()
    mock_row._mapping = {"order_id": 101, "amount": 250.0}
    mock_result.fetchmany.return_value = [mock_row]
    
    # 5. Try executing again -> should succeed
    exec_response_2 = await async_client.post(f"/api/execute_workspace/{workspace_id}")
    assert exec_response_2.status_code == 200
    resp_data = exec_response_2.json()
    assert resp_data["response_type"] == "data"
    assert resp_data["data"] == [{"order_id": 101, "amount": 250.0}]
    assert "1 rows returned" in resp_data["message"]
