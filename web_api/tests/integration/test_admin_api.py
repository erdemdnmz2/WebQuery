"""
Integration tests for admin router and service layer.
Verifies Role-Based Access Control (RBAC), database registration, and query approval workflows.
"""
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.future import select

from app import app
from app_database.models import Databases, QueryData, User, Workspace


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


async def create_user_and_login(async_client: AsyncClient, email: str, username: str, make_admin: bool = False) -> int:
    """
    Helper function to register, login, and optionally promote a user to admin.
    """
    register_data = {
        "username": username,
        "email": email,
        "password": "StrongPassword123!"
    }
    await async_client.post("/api/register", json=register_data)
    
    app_db = app.state.context.app_db
    user_id = 0
    if make_admin:
        async with app_db.get_app_db() as db:
            result = await db.execute(select(User).where(User.email == email))
            user = result.scalars().first()
            user_id = user.id
            
            from app_database.models import Databases, UserDatabaseAssociation
            db_res = await db.execute(select(Databases))
            all_dbs = db_res.scalars().all()
            for db_entry in all_dbs:
                assoc = UserDatabaseAssociation(
                    user_id=user.id,
                    database_id=db_entry.id,
                    role="ADMIN",
                    is_admin=True
                )
                db.add(assoc)
            await db.commit()
            
    login_data = {
        "email": email,
        "password": "StrongPassword123!"
    }
    await async_client.post("/api/login", json=login_data)
    
    if not make_admin:
        async with app_db.get_app_db() as db:
            result = await db.execute(select(User).where(User.email == email))
            user = result.scalars().first()
            user_id = user.id
            
    return user_id


@pytest.mark.asyncio
async def test_admin_rbac_restrictions(async_client: AsyncClient):
    """
    Tests that non-admin users are blocked from accessing administrative routes.
    """
    # 1. Login as regular user
    await create_user_and_login(async_client, "regular@example.com", "regular")
    
    # 2. Attempt to list queries waiting for approval -> should fail with 403 Forbidden
    resp_list = await async_client.get("/api/admin/queries_to_approve")
    assert resp_list.status_code == 403
    assert "Admin access required" in resp_list.json()["detail"]
    
    # 3. Attempt to approve a query -> should fail with 403 Forbidden
    resp_approve = await async_client.post("/api/admin/approve_query/1", json={"show_results": True})
    assert resp_approve.status_code == 403
    assert "Admin access required" in resp_approve.json()["detail"]
    
    # 4. Attempt to add a database -> should fail with 403 Forbidden
    db_payload = {
        "servername": "new-server",
        "database_name": "new-db",
        "tech_name": "mssql"
    }
    resp_add = await async_client.post("/api/admin/add_database", json=db_payload)
    assert resp_add.status_code == 403
    assert "Admin access required" in resp_add.json()["detail"]


@pytest.mark.asyncio
async def test_admin_database_registration(async_client: AsyncClient):
    """
    Tests registering databases by an admin, including duplicate checks.
    """
    app_db = app.state.context.app_db
    # Seed bootstrap database so the user can be an admin of at least one database
    async with app_db.get_app_db() as db:
        bootstrap_db = Databases(
            servername="bootstrap-server",
            database_name="bootstrap-db",
            technology="sqlite"
        )
        db.add(bootstrap_db)
        await db.commit()

    # 1. Login as admin
    await create_user_and_login(async_client, "admin1@example.com", "admin1", make_admin=True)
    
    # 2. Add database
    db_payload = {
        "servername": "prod-server",
        "database_name": "orders_db",
        "tech_name": "postgresql"
    }
    response = await async_client.post("/api/admin/add_database", json=db_payload)
    assert response.status_code == 200
    assert "added successfully" in response.json()["message"]
    
    # Verify database entry in metadata DB
    app_db = app.state.context.app_db
    async with app_db.get_app_db() as db:
        result = await db.execute(select(Databases).where(Databases.database_name == "orders_db"))
        db_entry = result.scalars().first()
        assert db_entry is not None
        assert db_entry.servername == "prod-server"
        assert db_entry.technology == "postgresql"
        
    # 3. Attempt to add duplicate database -> should fail with 400 Bad Request
    response_dup = await async_client.post("/api/admin/add_database", json=db_payload)
    assert response_dup.status_code == 400
    assert response_dup.json()["error_code"] == "DATABASE_ALREADY_EXISTS"
    assert "already exists" in response_dup.json()["message"]


@pytest.mark.asyncio
async def test_admin_query_approval_workflow(async_client: AsyncClient, mock_db_session):
    """
    Tests query approval and rejection flows, ensuring execution permissions update correctly.
    """
    _mock_session, mock_result = mock_db_session
    
    # 1. Register a regular user and create a workspace
    regular_client = AsyncClient(transport=async_client._transport, base_url="http://test")
    await create_user_and_login(regular_client, "user_req@example.com", "user_req")
    
    app_db = app.state.context.app_db
    db_uuid = None
    async with app_db.get_app_db() as db:
        from sqlalchemy.future import select

        from app_database.models import Databases, User, UserDatabaseAssociation
        test_db = Databases(
            servername="prod-server",
            database_name="orders_db",
            technology="mssql"
        )
        db.add(test_db)
        await db.commit()
        await db.refresh(test_db)
        db_uuid = test_db.uuid
        
        user_res = await db.execute(select(User).where(User.email == "user_req@example.com"))
        test_user = user_res.scalars().first()
        assoc = UserDatabaseAssociation(
            user_id=test_user.id,
            database_id=test_db.id,
            role="WRITER",
            is_admin=False
        )
        db.add(assoc)
        await db.commit()
        
    db_info = await app_db.get_db_info()
    app.state.context.db_provider.set_db_info(db_info)
    
    create_payload = {
        "name": "Audit Workspace",
        "query": "UPDATE items SET price = 10",
        "db_uuid": db_uuid
    }
    create_response = await regular_client.post("/api/workspaces", json=create_payload)
    workspace_id = create_response.json()["workspace_id"]
    
    # Simulate the query is flagged and waiting for approval in DB
    app_db = app.state.context.app_db
    async with app_db.get_app_db() as db:
        ws = await db.get(Workspace, workspace_id)
        qdata = await db.get(QueryData, ws.query_id)
        qdata.status = "waiting_for_approval"
        await db.commit()
        
    # 2. Login as admin
    admin_client = AsyncClient(transport=async_client._transport, base_url="http://test")
    await create_user_and_login(admin_client, "admin2@example.com", "admin2", make_admin=True)
    
    # 3. Get list of queries to approve -> should show the workspace
    list_response = await admin_client.get("/api/admin/queries_to_approve")
    assert list_response.status_code == 200
    approvals = list_response.json()["waiting_approvals"]
    assert len(approvals) == 1
    assert approvals[0]["workspace_id"] == workspace_id
    assert approvals[0]["query"] == "UPDATE items SET price = 10"
    
    # 4. Preview execution by admin (executes without changing status)
    mock_result.returns_rows = False
    mock_result.rowcount = 5
    
    preview_response = await admin_client.post(f"/api/admin/execute_for_preview/{workspace_id}")
    assert preview_response.status_code == 200
    assert preview_response.json()["response_type"] == "data"
    assert "5 rows affected" in preview_response.json()["message"]
    
    # Verify status remains "waiting_for_approval"
    async with app_db.get_app_db() as db:
        ws = await db.get(Workspace, workspace_id)
        qdata = await db.get(QueryData, ws.query_id)
        assert qdata.status == "waiting_for_approval"
        
    # 5. Approve query
    approve_payload = {"show_results": True}
    approve_response = await admin_client.post(f"/api/admin/approve_query/{workspace_id}", json=approve_payload)
    assert approve_response.status_code == 200
    assert approve_response.json()["success"] is True
    assert approve_response.json()["status"] == "approved_with_results"
    
    # Verify regular user can now execute it
    mock_result.returns_rows = False
    mock_result.rowcount = 5
    
    exec_response = await regular_client.post(f"/api/execute_workspace/{workspace_id}")
    assert exec_response.status_code == 200
    assert exec_response.json()["response_type"] == "data"
    assert "5 rows affected" in exec_response.json()["message"]


@pytest.mark.asyncio
async def test_admin_query_rejection(async_client: AsyncClient, mock_db_session):
    """
    Tests query rejection flow by an admin.
    """
    _mock_session, _mock_result = mock_db_session
    
    # 1. Create user and workspace
    regular_client = AsyncClient(transport=async_client._transport, base_url="http://test")
    await create_user_and_login(regular_client, "user_rej@example.com", "user_rej")
    
    app_db = app.state.context.app_db
    db_uuid = None
    async with app_db.get_app_db() as db:
        from sqlalchemy.future import select

        from app_database.models import Databases, User, UserDatabaseAssociation
        test_db = Databases(
            servername="prod-server",
            database_name="orders_db",
            technology="mssql"
        )
        db.add(test_db)
        await db.commit()
        await db.refresh(test_db)
        db_uuid = test_db.uuid
        
        user_res = await db.execute(select(User).where(User.email == "user_rej@example.com"))
        test_user = user_res.scalars().first()
        assoc = UserDatabaseAssociation(
            user_id=test_user.id,
            database_id=test_db.id,
            role="WRITER",
            is_admin=False
        )
        db.add(assoc)
        await db.commit()
        
    db_info = await app_db.get_db_info()
    app.state.context.db_provider.set_db_info(db_info)
    
    create_payload = {
        "name": "Rejected Workspace",
        "query": "DROP TABLE critical_table",
        "db_uuid": db_uuid
    }
    create_response = await regular_client.post("/api/workspaces", json=create_payload)
    workspace_id = create_response.json()["workspace_id"]
    
    # Simulate query is waiting for approval
    app_db = app.state.context.app_db
    async with app_db.get_app_db() as db:
        ws = await db.get(Workspace, workspace_id)
        qdata = await db.get(QueryData, ws.query_id)
        qdata.status = "waiting_for_approval"
        await db.commit()
        
    # 2. Login as admin
    admin_client = AsyncClient(transport=async_client._transport, base_url="http://test")
    await create_user_and_login(admin_client, "admin3@example.com", "admin3", make_admin=True)
    
    # 3. Reject query
    reject_response = await admin_client.post(f"/api/admin/reject_query/{workspace_id}")
    assert reject_response.status_code == 200
    
    # Verify status changed to "rejected"
    async with app_db.get_app_db() as db:
        ws = await db.get(Workspace, workspace_id)
        qdata = await db.get(QueryData, ws.query_id)
        assert qdata.status == "rejected"
        assert ws.description == "Rejected by admin"
        
    # Verify regular user execution remains blocked (returns 400 Bad Request / QUERY_REJECTED_BY_ANALYZER)
    exec_response = await regular_client.post(f"/api/execute_workspace/{workspace_id}")
    assert exec_response.status_code == 400
    assert exec_response.json()["error_code"] == "QUERY_REJECTED_BY_ANALYZER"
