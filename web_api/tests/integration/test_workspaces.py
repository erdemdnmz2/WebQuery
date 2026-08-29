"""
Integration tests for workspaces router and service layer.
Verifies Workspace CRUD operations, ownership validation, and execution rules.
"""
from contextlib import asynccontextmanager
from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app import app
from app_database.models import (
    Databases,
    QueryData,
    User,
    UserDatabaseAssociation,
    Workspace,
)
from tests.conftest import make_target_session_mock


@pytest.fixture
def mock_db_session():
    """
    Fixture that patches DatabaseProvider.get_session to return a mock session.
    """
    mock_session, mock_result = make_target_session_mock()
    
    @asynccontextmanager
    async def fake_get_session(user, db_uuid, tier="ro"):
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
    # 1. Setup Database
    app_db = app.state.context.app_db
    db_uuid = None
    db_id = None
    async with app_db.get_app_db() as db:
        test_db = Databases(
            servername="localhost",
            database_name="my_db",
            technology="postgresql"
        )
        db.add(test_db)
        await db.commit()
        await db.refresh(test_db)
        db_uuid = test_db.uuid
        db_id = test_db.id

    db_info = await app_db.get_db_info()
    app.state.context.db_provider.set_db_info(db_info)

    # 2. Register and login
    await create_user_and_login(async_client, "user1@example.com", "user1")
    
    # Associate user
    async with app_db.get_app_db() as db:
        user_res = await db.execute(select(User).where(User.email == "user1@example.com"))
        test_user = user_res.scalars().first()
        assoc = UserDatabaseAssociation(
            user_id=test_user.id,
            database_id=db_id,
            role="READER",
            is_admin=False
        )
        db.add(assoc)
        await db.commit()

    # 3. Create workspace
    create_payload = {
        "name": "My Workspace",
        "query": "SELECT * FROM my_table",
        "db_uuid": db_uuid
    }
    create_response = await async_client.post("/api/workspaces", json=create_payload)
    assert create_response.status_code == 200, f"Failed to create workspace: {create_response.text}"
    create_data = create_response.json()
    assert create_data["success"] is True
    workspace_id = create_data["workspace_id"]
    
    # 4. Get workspace details
    detail_response = await async_client.get(f"/api/get_workspace_by_id/{workspace_id}")
    assert detail_response.status_code == 200
    detail_data = detail_response.json()
    assert detail_data["name"] == "My Workspace"
    assert detail_data["query"] == "SELECT * FROM my_table"
    assert detail_data["servername"] == "localhost"
    assert detail_data["database_name"] == "my_db"
    assert detail_data["status"] == "saved_in_workspace"  # Newly created queries default to saved_in_workspace
    
    # 5. List workspaces
    list_response = await async_client.get("/api/workspaces")
    assert list_response.status_code == 200
    list_data = list_response.json()
    assert len(list_data["workspaces"]) == 1
    assert list_data["workspaces"][0]["id"] == workspace_id
    
    # 6. Update workspace query (status is server-owned; see test_workspace_approval_lock)
    update_payload = {"query": "SELECT count(*) FROM my_table"}
    update_response = await async_client.put(f"/api/workspaces/{workspace_id}", json=update_payload)
    assert update_response.status_code == 200
    
    # Verify update
    detail_response_2 = await async_client.get(f"/api/get_workspace_by_id/{workspace_id}")
    detail_data_2 = detail_response_2.json()
    assert detail_data_2["query"] == "SELECT count(*) FROM my_table"
    
    # 7. Delete workspace
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
    # Setup database
    app_db = app.state.context.app_db
    db_uuid = None
    db_id = None
    async with app_db.get_app_db() as db:
        test_db = Databases(
            servername="localhost",
            database_name="db",
            technology="postgresql"
        )
        db.add(test_db)
        await db.commit()
        await db.refresh(test_db)
        db_uuid = test_db.uuid
        db_id = test_db.id

    db_info = await app_db.get_db_info()
    app.state.context.db_provider.set_db_info(db_info)

    # 1. Login user1 and create a workspace
    await create_user_and_login(async_client, "owner@example.com", "owner")
    
    # Associate user
    async with app_db.get_app_db() as db:
        user_res = await db.execute(select(User).where(User.email == "owner@example.com"))
        test_user = user_res.scalars().first()
        assoc = UserDatabaseAssociation(
            user_id=test_user.id,
            database_id=db_id,
            role="READER",
            is_admin=False
        )
        db.add(assoc)
        await db.commit()

    create_payload = {
        "name": "Owner Workspace",
        "query": "SELECT 1",
        "db_uuid": db_uuid
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
    update_payload = {"query": "DROP TABLE users"}
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
    _mock_session, mock_result = mock_db_session
    
    app_db = app.state.context.app_db
    db_uuid = None
    db_id = None
    async with app_db.get_app_db() as db:
        test_db = Databases(
            servername="localhost",
            database_name="sales_db",
            technology="postgresql"
        )
        db.add(test_db)
        await db.commit()
        await db.refresh(test_db)
        db_uuid = test_db.uuid
        db_id = test_db.id

    db_info = await app_db.get_db_info()
    app.state.context.db_provider.set_db_info(db_info)

    # 1. Login and create workspace
    await create_user_and_login(async_client, "exec@example.com", "exec_user")
    
    # Associate user
    async with app_db.get_app_db() as db:
        user_res = await db.execute(select(User).where(User.email == "exec@example.com"))
        test_user = user_res.scalars().first()
        assoc = UserDatabaseAssociation(
            user_id=test_user.id,
            database_id=db_id,
            role="READER",
            is_admin=False
        )
        db.add(assoc)
        await db.commit()

    create_payload = {
        "name": "Execution Workspace",
        "query": "SELECT * FROM orders",
        "db_uuid": db_uuid
    }
    create_response = await async_client.post("/api/workspaces", json=create_payload)
    workspace_id = create_response.json()["workspace_id"]
    
    # 2. Try to execute immediately (default is saved_in_workspace/unapproved) -> should fail with 400 Bad Request
    exec_response = await async_client.post(f"/api/execute_workspace/{workspace_id}")
    assert exec_response.status_code == 400
    assert exec_response.json()["error_code"] == "QUERY_REJECTED_BY_ANALYZER"
    
    # 3. Manually approve workspace with show_results=True in metadata DB
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


# --- P0-3: approval bypass through PUT /api/workspaces/{id} -----------------
#
# PUT accepted {query, status} with no state machine at all. An owner could get
# a harmless risky query approved (show_results=True,
# status="approved_with_results"), then swap the SQL for an unrestricted
# UPDATE/DELETE: execute_workspace only re-checks show_results and status, so the
# approval-requiring analyzer classes were skipped entirely. The same hole let a
# client self-approve by sending status directly.


async def _register_db_and_workspace(async_client: AsyncClient, email: str, query: str):
    """Create a database, an associated WRITER user, and one saved workspace."""
    app_db = app.state.context.app_db
    async with app_db.get_app_db() as db:
        test_db = Databases(
            servername="localhost", database_name="lock_db", technology="postgresql"
        )
        db.add(test_db)
        await db.commit()
        await db.refresh(test_db)
        db_uuid, db_id = test_db.uuid, test_db.id

    app.state.context.db_provider.set_db_info(await app_db.get_db_info())
    await create_user_and_login(async_client, email, email.split("@")[0])

    async with app_db.get_app_db() as db:
        user_res = await db.execute(select(User).where(User.email == email))
        db.add(
            UserDatabaseAssociation(
                user_id=user_res.scalars().first().id,
                database_id=db_id,
                role="WRITER",
                is_admin=False,
            )
        )
        await db.commit()

    created = await async_client.post(
        "/api/workspaces",
        json={"name": "Locked", "query": query, "db_uuid": db_uuid},
    )
    return created.json()["workspace_id"]


async def _set_status(workspace_id: int, status: str, show_results: bool | None):
    app_db = app.state.context.app_db
    async with app_db.get_app_db() as db:
        ws = await db.get(Workspace, workspace_id)
        ws.show_results = show_results
        query_data = await db.get(QueryData, ws.query_id)
        query_data.status = status
        await db.commit()


async def _read_state(workspace_id: int) -> tuple[str, str, bool | None]:
    app_db = app.state.context.app_db
    async with app_db.get_app_db() as db:
        ws = await db.get(Workspace, workspace_id)
        query_data = await db.get(QueryData, ws.query_id)
        return query_data.query, query_data.status, ws.show_results


@pytest.mark.asyncio
async def test_client_cannot_set_workspace_status(async_client: AsyncClient):
    """Sending `status` must fail loudly, not be silently ignored."""
    workspace_id = await _register_db_and_workspace(
        async_client, "statusclient@example.com", "SELECT 1"
    )

    response = await async_client.put(
        f"/api/workspaces/{workspace_id}",
        json={"query": "SELECT 2", "status": "approved_with_results"},
    )

    assert response.status_code == 422
    query, status_value, _ = await _read_state(workspace_id)
    assert query == "SELECT 1"
    assert status_value == "saved_in_workspace"


@pytest.mark.asyncio
async def test_approved_workspace_sql_cannot_be_rewritten(async_client: AsyncClient):
    """The bypass itself: one approval must not cover a different statement."""
    workspace_id = await _register_db_and_workspace(
        async_client, "approved@example.com", "SELECT * FROM orders"
    )
    await _set_status(workspace_id, "approved_with_results", True)

    response = await async_client.put(
        f"/api/workspaces/{workspace_id}",
        json={"query": "DELETE FROM orders"},
    )

    assert response.status_code == 409
    assert response.json()["error_code"] == "WORKSPACE_NOT_EDITABLE"
    query, status_value, show_results = await _read_state(workspace_id)
    assert query == "SELECT * FROM orders"
    assert status_value == "approved_with_results"
    assert show_results is True


@pytest.mark.asyncio
async def test_pending_workspace_sql_cannot_be_rewritten(async_client: AsyncClient):
    """TOCTOU: the approver must decide on the text they were shown."""
    workspace_id = await _register_db_and_workspace(
        async_client, "pending@example.com", "UPDATE orders SET total = 1"
    )
    await _set_status(workspace_id, "waiting_for_approval", None)

    response = await async_client.put(
        f"/api/workspaces/{workspace_id}",
        json={"query": "DELETE FROM orders"},
    )

    assert response.status_code == 409
    query, _, _ = await _read_state(workspace_id)
    assert query == "UPDATE orders SET total = 1"


@pytest.mark.asyncio
async def test_approved_and_executed_workspace_is_locked(async_client: AsyncClient):
    workspace_id = await _register_db_and_workspace(
        async_client, "executed@example.com", "SELECT 1"
    )
    await _set_status(workspace_id, "approved_and_executed", False)

    response = await async_client.put(
        f"/api/workspaces/{workspace_id}", json={"query": "SELECT 2"}
    )

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_rejected_workspace_can_be_edited_and_returns_to_draft(
    async_client: AsyncClient,
):
    """A rejected query is fixable; editing it resets it to a plain draft."""
    workspace_id = await _register_db_and_workspace(
        async_client, "rejected@example.com", "DELETE FROM orders"
    )
    await _set_status(workspace_id, "rejected", None)

    response = await async_client.put(
        f"/api/workspaces/{workspace_id}",
        json={"query": "DELETE FROM orders WHERE id = 1"},
    )

    assert response.status_code == 200
    query, status_value, show_results = await _read_state(workspace_id)
    assert query == "DELETE FROM orders WHERE id = 1"
    assert status_value == "saved_in_workspace"
    assert show_results is None


@pytest.mark.asyncio
async def test_editing_a_draft_clears_any_shared_results(async_client: AsyncClient):
    """New SQL must never inherit an old decision's `show_results`."""
    workspace_id = await _register_db_and_workspace(
        async_client, "draftedit@example.com", "SELECT 1"
    )
    await _set_status(workspace_id, "saved_in_workspace", True)

    response = await async_client.put(
        f"/api/workspaces/{workspace_id}", json={"query": "SELECT 2"}
    )

    assert response.status_code == 200
    query, status_value, show_results = await _read_state(workspace_id)
    assert query == "SELECT 2"
    assert status_value == "saved_in_workspace"
    assert show_results is None
