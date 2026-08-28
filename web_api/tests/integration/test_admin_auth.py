from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app import app
from app_database.models import Databases, User


@pytest.fixture
def mock_db_session_auth():
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_session.execute.return_value = mock_result
    
    @asynccontextmanager
    async def fake_get_session(user, db_uuid, tier="ro"):
        yield mock_session
        
    with patch("database_provider.DatabaseProvider.get_session", side_effect=fake_get_session):
        yield mock_session, mock_result

@pytest.mark.asyncio
async def test_admin_user_association_and_visibility(async_client: AsyncClient, mock_db_session_auth):
    """
    Tests database visibility and query execution before and after admin associates user to database.
    """
    _mock_session, mock_result = mock_db_session_auth
    mock_result.returns_rows = True
    mock_row = MagicMock()
    mock_row._mapping = {"id": 1}
    mock_result.fetchmany.return_value = [mock_row]

    # 1. Setup mock database
    app_db = app.state.context.app_db
    db_uuid = None
    db_id = None
    async with app_db.get_app_db() as db:
        test_db = Databases(
            servername="auth-server",
            database_name="auth-db",
            technology="postgresql"
        )
        db.add(test_db)
        await db.commit()
        await db.refresh(test_db)
        db_uuid = test_db.uuid
        db_id = test_db.id

    db_info = await app_db.get_db_info()
    app.state.context.db_provider.set_db_info(db_info)

    # 2. Register and login regular user
    reg_client = AsyncClient(transport=async_client._transport, base_url="http://test")
    await reg_client.post("/api/register", json={
        "username": "authuser",
        "email": "authuser@example.com",
        "password": "StrongPassword123!"
    })
    await reg_client.post("/api/login", json={
        "email": "authuser@example.com",
        "password": "StrongPassword123!"
    })

    # 3. Before association, user should NOT see the database in database_information
    info_resp = await reg_client.get("/api/database_information")
    assert info_resp.status_code == 200
    assert "auth-server" not in info_resp.json()["db_info"]

    # 4. Before association, executing query should fail (Permission Denied)
    exec_resp = await reg_client.post("/api/execute_query", json={
        "query": "SELECT 1",
        "db_uuid": db_uuid
    })
    assert exec_resp.status_code == 400
    assert "permission to access this database" in exec_resp.text

    # 5. Login as admin and associate the user
    admin_client = AsyncClient(transport=async_client._transport, base_url="http://test")
    await admin_client.post("/api/register", json={
        "username": "authadmin",
        "email": "authadmin@example.com",
        "password": "StrongPassword123!"
    })
    # Make admin
    async with app_db.get_app_db() as db:
        admin_res = await db.execute(select(User).where(User.email == "authadmin@example.com"))
        admin_user = admin_res.scalars().first()
        
        db_res = await db.execute(select(Databases).where(Databases.uuid == db_uuid))
        db_entry = db_res.scalars().first()
        
        from app_database.models import UserDatabaseAssociation
        assoc = UserDatabaseAssociation(
            user_id=admin_user.id,
            database_id=db_entry.id,
            role="ADMIN",
            is_admin=True
        )
        db.add(assoc)
        await db.commit()

    await admin_client.post("/api/login", json={
        "email": "authadmin@example.com",
        "password": "StrongPassword123!"
    })

    # Get user id of regular user
    reg_user_id = None
    async with app_db.get_app_db() as db:
        user_res = await db.execute(select(User).where(User.email == "authuser@example.com"))
        reg_user = user_res.scalars().first()
        reg_user_id = reg_user.id

    # Associate as WRITER
    assoc_resp = await admin_client.post("/api/admin/associate_user", json={
        "user_id": reg_user_id,
        "database_id": db_id,
        "role": "WRITER"
    })
    assert assoc_resp.status_code == 200

    # 6. After association, regular user should see the database in database_information
    info_resp_after = await reg_client.get("/api/database_information")
    assert info_resp_after.status_code == 200
    assert "auth-server" in info_resp_after.json()["db_info"]
    databases_list = info_resp_after.json()["db_info"]["auth-server"]["databases"]
    assert len(databases_list) == 1
    assert databases_list[0]["uuid"] == db_uuid

    # 7. After association, regular user should execute SELECT queries successfully
    exec_resp_after = await reg_client.post("/api/execute_query", json={
        "query": "SELECT 1",
        "db_uuid": db_uuid
    })
    assert exec_resp_after.status_code == 200
