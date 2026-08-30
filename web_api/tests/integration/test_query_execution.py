"""
Integration tests for query execution endpoints.
Verifies SELECT and DML/non-SELECT query execution paths, safety, and Role-Based Access Control (RBAC).
"""
from contextlib import asynccontextmanager
from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app import app
from app_database.models import Databases, User, UserDatabaseAssociation
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

@pytest.mark.asyncio
async def test_select_query_execution(async_client: AsyncClient, mock_db_session):
    """
    Test that a SELECT query returns data successfully for a user with READER role.
    """
    _mock_session, mock_result = mock_db_session
    
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
    _mock_session, mock_result = mock_db_session
    
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
    _mock_session, _mock_result = mock_db_session
    
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
    assert response.status_code == 403
    assert response.json()["error_code"] == "QUERY_ROLE_DENIED"
    assert "not authorized to execute" in response.text

@pytest.mark.asyncio
async def test_writer_blocked_from_ddl(async_client: AsyncClient, mock_db_session):
    """
    Test that a WRITER user is blocked from executing DDL queries.
    """
    _mock_session, _mock_result = mock_db_session
    
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
    assert response.status_code == 403
    assert response.json()["error_code"] == "QUERY_ROLE_DENIED"
    assert "not authorized to execute" in response.text


@pytest.mark.asyncio
async def test_multi_role_query_execution(async_client: AsyncClient, mock_db_session):
    """
    Test that a user with multiple comma-separated roles ("READER,WRITER")
    can execute SELECT and DML queries but is blocked from DDL queries.
    """
    _mock_session, mock_result = mock_db_session

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
    assert response_ddl.status_code == 403
    assert response_ddl.json()["error_code"] == "QUERY_ROLE_DENIED"
    assert "not authorized to execute" in response_ddl.text


async def _register_admin_on_new_database(
    async_client: AsyncClient, email: str, username: str
) -> str:
    """Register a target database and an ADMIN user associated with it."""
    app_db = app.state.context.app_db
    async with app_db.get_app_db() as db:
        target = Databases(
            servername="hardblock-server",
            database_name=f"hardblock-{username}",
            technology="postgresql",
        )
        db.add(target)
        await db.commit()
        await db.refresh(target)
        db_uuid = target.uuid
        database_id = target.id

    app.state.context.db_provider.set_db_info(await app_db.get_db_info())

    await async_client.post(
        "/api/register",
        json={"username": username, "email": email, "password": "StrongPassword123!"},
    )
    await async_client.post(
        "/api/login", json={"email": email, "password": "StrongPassword123!"}
    )

    async with app_db.get_app_db() as db:
        user_res = await db.execute(select(User).where(User.email == email))
        user = user_res.scalars().first()
        db.add(
            UserDatabaseAssociation(
                user_id=user.id,
                database_id=database_id,
                role="ADMIN",
                is_admin=True,
            )
        )
        await db.commit()

    return db_uuid


@pytest.mark.asyncio
async def test_admin_cannot_skip_a_hard_blocked_query(
    async_client: AsyncClient, mock_db_session
):
    """
    The administrator bypass covers the approval requirement, not the security
    check. Filesystem access has no supported path through WebQuery, so "who is
    asking" is not a relevant question for it.
    """
    mock_session, _mock_result = mock_db_session
    db_uuid = await _register_admin_on_new_database(
        async_client, "hardblock-admin@example.com", "hardblockadmin"
    )

    response = await async_client.post(
        "/api/execute_query",
        json={"query": "SELECT pg_read_file('/etc/passwd')", "db_uuid": db_uuid},
    )

    assert response.status_code == 400
    assert response.json()["error_code"] == "QUERY_BLOCKED"
    assert "pg_read_file" in response.text
    mock_session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_admin_still_skips_approval_for_a_reviewable_risk(
    async_client: AsyncClient, mock_db_session
):
    """A WHERE-less DELETE stays an approval question, and ADMIN still runs it."""
    mock_session, mock_result = mock_db_session
    mock_result.returns_rows = False
    mock_result.rowcount = 3
    db_uuid = await _register_admin_on_new_database(
        async_client, "reviewable-admin@example.com", "reviewableadmin"
    )

    response = await async_client.post(
        "/api/execute_query",
        json={"query": "DELETE FROM orders", "db_uuid": db_uuid},
    )

    assert response.status_code == 200
    mock_session.execute.assert_called_once()


# --- P1-3: GET /api/masking_rules performed no access check ------------------
#
# The endpoint resolved a database by UUID and returned its masked column names
# with no association check at all. Any authenticated user holding a UUID could
# enumerate a foreign database's sensitive columns (`salary`, `tckn`, `iban`, …).


async def _register_and_login(async_client: AsyncClient, email: str, username: str) -> None:
    credentials = {"email": email, "password": "StrongPassword123!"}
    await async_client.post(
        "/api/register", json={"username": username, **credentials}
    )
    await async_client.post("/api/login", json=credentials)


@pytest.mark.asyncio
async def test_masking_rules_requires_an_association(async_client: AsyncClient):
    from app_database.models import MaskingRule

    app_db = app.state.context.app_db
    async with app_db.get_app_db() as db:
        target = Databases(
            servername="masking-server",
            database_name="masking-db",
            technology="postgresql",
        )
        db.add(target)
        await db.commit()
        await db.refresh(target)
        db_uuid, db_id = str(target.uuid), target.id
        db.add(
            MaskingRule(
                database_id=db_id,
                table_name="Employees",
                column_name="salary",
                masking_type="full",
                is_active=True,
            )
        )
        await db.commit()

    app.state.context.db_provider.set_db_info(await app_db.get_db_info())

    # An authenticated user with no association must be refused, not answered
    # with an empty list — "no rules" and "no access" have to stay distinct.
    await _register_and_login(async_client, "outsider@example.com", "outsider")
    denied = await async_client.get("/api/masking_rules", params={"db_uuid": db_uuid})
    assert denied.status_code == 403
    assert denied.json()["error_code"] == "DATABASE_ACCESS_DENIED"
    assert "salary" not in denied.text

    # An associated user still gets the list.
    await _register_and_login(async_client, "insider@example.com", "insider")
    async with app_db.get_app_db() as db:
        insider = (
            await db.execute(select(User).where(User.email == "insider@example.com"))
        ).scalars().first()
        db.add(
            UserDatabaseAssociation(
                user_id=insider.id, database_id=db_id, role="READER", is_admin=False
            )
        )
        await db.commit()

    allowed = await async_client.get("/api/masking_rules", params={"db_uuid": db_uuid})
    assert allowed.status_code == 200
    assert allowed.json() == ["salary"]
