"""
Integration tests for query execution endpoints.
Verifies SELECT and DML/non-SELECT query execution paths, safety, and Role-Based Access Control (RBAC).
"""
import pytest
from httpx import AsyncClient
from unittest.mock import MagicMock, AsyncMock, patch
from contextlib import asynccontextmanager
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
async def test_select_query_execution(async_client: AsyncClient, mock_db_session):
    """
    Test that a SELECT query returns data successfully for a user with READER role.
    """
    mock_session, mock_result = mock_db_session
    
    # 1. Setup mock database in metadata DB
    app_db = app.state.context.app_db
    db_uuid = None
    async with app_db.get_app_db() as db:
        test_db = Databases(
            servername="test-server",
            database_name="test-db",
            technology="postgresql"
        )
        db.add(test_db)
        await db.commit()
        await db.refresh(test_db)
        db_uuid = test_db.uuid
        
    db_info = await app_db.get_db_info()
    app.state.context.db_provider.set_db_info(db_info)
    
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
    
    # Create UserDatabaseAssociation as READER
    async with app_db.get_app_db() as db:
        user_res = await db.execute(select(User).where(User.email == "query@example.com"))
        test_user = user_res.scalars().first()
        
        db_entry_res = await db.execute(select(Databases).where(Databases.uuid == db_uuid))
        db_entry = db_entry_res.scalars().first()
        
        assoc = UserDatabaseAssociation(
            user_id=test_user.id,
            database_id=db_entry.id,
            role="READER",
            is_admin=False
        )
        db.add(assoc)
        await db.commit()
    
    # 3. Configure mock result for SELECT
    mock_result.returns_rows = True
    mock_row = MagicMock()
    mock_row._mapping = {"id": 1, "name": "John Doe"}
    mock_result.fetchmany.return_value = [mock_row]
    
    # 4. Execute the query via API
    query_payload = {
        "query": "SELECT * FROM users",
        "db_uuid": db_uuid
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
    Test that a DML query executes successfully for a user with WRITER role.
    """
    mock_session, mock_result = mock_db_session
    
    app_db = app.state.context.app_db
    db_uuid = None
    async with app_db.get_app_db() as db:
        test_db = Databases(
            servername="test-server",
            database_name="test-db",
            technology="postgresql"
        )
        db.add(test_db)
        await db.commit()
        await db.refresh(test_db)
        db_uuid = test_db.uuid

    db_info = await app_db.get_db_info()
    app.state.context.db_provider.set_db_info(db_info)

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
    
    # Create UserDatabaseAssociation as WRITER
    async with app_db.get_app_db() as db:
        db_res = await db.execute(select(Databases).where(Databases.uuid == db_uuid))
        db_entry = db_res.scalars().first()
        
        user_res = await db.execute(select(User).where(User.email == "query2@example.com"))
        test_user = user_res.scalars().first()
        
        assoc = UserDatabaseAssociation(
            user_id=test_user.id,
            database_id=db_entry.id,
            role="WRITER",
            is_admin=False
        )
        db.add(assoc)
        await db.commit()
        
    mock_result.returns_rows = False
    mock_result.rowcount = 3
    
    # Execute the query via API
    query_payload = {
        "query": "UPDATE users SET active = 1 WHERE age > 30",
        "db_uuid": db_uuid
    }
    response = await async_client.post("/api/execute_query", json=query_payload)
    assert response.status_code == 200, f"Query execution failed: {response.text}"
    
    resp_data = response.json()
    assert resp_data["response_type"] == "data"
    assert resp_data["data"] == []
    assert resp_data["message"] == "3 rows affected"

@pytest.mark.asyncio
async def test_reader_blocked_from_dml(async_client: AsyncClient, mock_db_session):
    """
    Test that a READER user is blocked from executing DML queries.
    """
    mock_session, mock_result = mock_db_session
    
    app_db = app.state.context.app_db
    db_uuid = None
    async with app_db.get_app_db() as db:
        test_db = Databases(
            servername="test-server",
            database_name="test-db",
            technology="postgresql"
        )
        db.add(test_db)
        await db.commit()
        await db.refresh(test_db)
        db_uuid = test_db.uuid

    db_info = await app_db.get_db_info()
    app.state.context.db_provider.set_db_info(db_info)

    # Register and login
    register_data = {
        "username": "queryuser3",
        "email": "query3@example.com",
        "password": "StrongPassword123!"
    }
    await async_client.post("/api/register", json=register_data)
    
    login_data = {
        "email": "query3@example.com",
        "password": "StrongPassword123!"
    }
    await async_client.post("/api/login", json=login_data)
    
    # Create UserDatabaseAssociation as READER
    async with app_db.get_app_db() as db:
        db_res = await db.execute(select(Databases).where(Databases.uuid == db_uuid))
        db_entry = db_res.scalars().first()
        
        user_res = await db.execute(select(User).where(User.email == "query3@example.com"))
        test_user = user_res.scalars().first()
        
        assoc = UserDatabaseAssociation(
            user_id=test_user.id,
            database_id=db_entry.id,
            role="READER",
            is_admin=False
        )
        db.add(assoc)
        await db.commit()
        
    query_payload = {
        "query": "UPDATE users SET active = 1",
        "db_uuid": db_uuid
    }
    response = await async_client.post("/api/execute_query", json=query_payload)
    assert response.status_code == 400
    assert "not authorized to execute" in response.text

@pytest.mark.asyncio
async def test_writer_blocked_from_ddl(async_client: AsyncClient, mock_db_session):
    """
    Test that a WRITER user is blocked from executing DDL queries.
    """
    mock_session, mock_result = mock_db_session
    
    app_db = app.state.context.app_db
    db_uuid = None
    async with app_db.get_app_db() as db:
        test_db = Databases(
            servername="test-server",
            database_name="test-db",
            technology="postgresql"
        )
        db.add(test_db)
        await db.commit()
        await db.refresh(test_db)
        db_uuid = test_db.uuid

    db_info = await app_db.get_db_info()
    app.state.context.db_provider.set_db_info(db_info)

    # Register and login
    register_data = {
        "username": "queryuser4",
        "email": "query4@example.com",
        "password": "StrongPassword123!"
    }
    await async_client.post("/api/register", json=register_data)
    
    login_data = {
        "email": "query4@example.com",
        "password": "StrongPassword123!"
    }
    await async_client.post("/api/login", json=login_data)
    
    # Create UserDatabaseAssociation as WRITER
    async with app_db.get_app_db() as db:
        db_res = await db.execute(select(Databases).where(Databases.uuid == db_uuid))
        db_entry = db_res.scalars().first()
        
        user_res = await db.execute(select(User).where(User.email == "query4@example.com"))
        test_user = user_res.scalars().first()
        
        assoc = UserDatabaseAssociation(
            user_id=test_user.id,
            database_id=db_entry.id,
            role="WRITER",
            is_admin=False
        )
        db.add(assoc)
        await db.commit()
        
    query_payload = {
        "query": "DROP TABLE users",
        "db_uuid": db_uuid
    }
    response = await async_client.post("/api/execute_query", json=query_payload)
    assert response.status_code == 400
    assert "not authorized to execute" in response.text


@pytest.mark.asyncio
async def test_multi_role_query_execution(async_client: AsyncClient, mock_db_session):
    """
    Test that a user with multiple comma-separated roles ("READER,WRITER")
    can execute SELECT and DML queries but is blocked from DDL queries.
    """
    mock_session, mock_result = mock_db_session

    app_db = app.state.context.app_db
    db_uuid = None
    db_id = None
    async with app_db.get_app_db() as db:
        test_db = Databases(
            servername="test-server-multi",
            database_name="test-db-multi",
            technology="postgresql"
        )
        db.add(test_db)
        await db.commit()
        await db.refresh(test_db)
        db_uuid = test_db.uuid
        db_id = test_db.id

    db_info = await app_db.get_db_info()
    app.state.context.db_provider.set_db_info(db_info)

    # Register and login
    register_data = {
        "username": "queryuser_multi",
        "email": "query_multi@example.com",
        "password": "StrongPassword123!"
    }
    await async_client.post("/api/register", json=register_data)

    login_data = {
        "email": "query_multi@example.com",
        "password": "StrongPassword123!"
    }
    await async_client.post("/api/login", json=login_data)

    # Associate user with multiple roles: READER,WRITER
    async with app_db.get_app_db() as db:
        user_res = await db.execute(select(User).where(User.email == "query_multi@example.com"))
        test_user = user_res.scalars().first()

        assoc = UserDatabaseAssociation(
            user_id=test_user.id,
            database_id=db_id,
            role="READER,WRITER",
            is_admin=False
        )
        db.add(assoc)
        await db.commit()

    # 1. Test SELECT query (Allowed by READER/WRITER)
    mock_result.returns_rows = True
    mock_row = MagicMock()
    mock_row._mapping = {"id": 1, "name": "Test"}
    mock_result.fetchmany.return_value = [mock_row]

    sel_payload = {
        "query": "SELECT * FROM items",
        "db_uuid": db_uuid
    }
    response_sel = await async_client.post("/api/execute_query", json=sel_payload)
    assert response_sel.status_code == 200

    # 2. Test DML query (Allowed by WRITER)
    mock_result.returns_rows = False
    mock_result.rowcount = 1

    dml_payload = {
        "query": "UPDATE items SET name = 'Updated' WHERE id = 1",
        "db_uuid": db_uuid
    }
    response_dml = await async_client.post("/api/execute_query", json=dml_payload)
    assert response_dml.status_code == 200

    # 3. Test DDL query (Blocked because ADMIN is not in roles)
    ddl_payload = {
        "query": "CREATE TABLE test_table (id INT)",
        "db_uuid": db_uuid
    }
    response_ddl = await async_client.post("/api/execute_query", json=ddl_payload)
    assert response_ddl.status_code == 400
    assert "not authorized to execute" in response_ddl.text
