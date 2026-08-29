from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, text
from sqlalchemy.future import select

from app import app
from app_database.models import (
    Databases,
    MaskingRule,
    User,
)


@pytest.fixture
def mock_db_session():
    """
    Fixture that patches DatabaseProvider.get_session to return a mock session.
    """
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_session.execute.return_value = mock_result
    
    @asynccontextmanager
    async def fake_get_session(user, db_uuid, tier="ro"):
        yield mock_session
        
    with patch("database_provider.DatabaseProvider.get_session", side_effect=fake_get_session):
        yield mock_session, mock_result

async def create_user_and_login(
    async_client: AsyncClient,
    email: str,
    username: str,
    make_admin: bool = False,
    make_owner: bool = False,
) -> int:
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
    if make_admin or make_owner:
        async with app_db.get_app_db() as db:
            result = await db.execute(select(User).where(User.email == email))
            user = result.scalars().first()
            user_id = user.id
            user.is_platform_owner = make_owner
            
            from app_database.models import Databases, UserDatabaseAssociation
            db_res = await db.execute(select(Databases))
            all_dbs = db_res.scalars().all()
            for db_entry in all_dbs if make_admin else []:
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
    
    if not make_admin and not make_owner:
        async with app_db.get_app_db() as db:
            result = await db.execute(select(User).where(User.email == email))
            user = result.scalars().first()
            user_id = user.id
            
    return user_id

@pytest.mark.asyncio
async def test_jwt_blacklist_on_logout(async_client: AsyncClient):
    """
    Tests that logging out invalidates the active session and prevents token reuse (JTI blacklisting).
    """
    # 1. Register and login
    await create_user_and_login(async_client, "logout_test@example.com", "logout_user")
    
    # 2. Verify we can access workspace list (authenticated)
    resp = await async_client.get("/api/workspaces")
    assert resp.status_code == 200
    
    # 3. Logout
    logout_resp = await async_client.post("/api/logout")
    assert logout_resp.status_code == 200
    
    # 4. Attempt to access workspace list again -> should be blocked with 401 Unauthorized
    resp_after = await async_client.get("/api/workspaces")
    assert resp_after.status_code == 401

@pytest.mark.asyncio
async def test_encryption_at_rest(async_client: AsyncClient):
    """
    Verifies that sensitive data (DB passwords and SQL queries) are encrypted at rest (AES-256)
    but transparently decrypted when retrieved via ORM.
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
    
    # 1. Add database as OWNER with an explicit first DB ADMIN.
    admin_client = AsyncClient(transport=async_client._transport, base_url="http://test")
    await create_user_and_login(admin_client, "enc_owner@example.com", "enc_owner", make_owner=True)
    async with app_db.get_app_db() as db:
        first_admin = (
            await db.execute(select(User).where(User.email == "enc_owner@example.com"))
        ).scalars().one()
        first_admin_id = first_admin.id
    
    db_payload = {
        "servername": "secure-server",
        "database_name": "secure_db",
        "tech_name": "postgresql",
        "connection_mode": "ro",
        "initial_admin_user_id": first_admin_id,
        "username_ro": "secure_ro",
        "password_ro": "secret-for-encryption-test",
    }
    resp = await admin_client.post("/api/owner/databases", json=db_payload)
    assert resp.status_code == 201
    
    # 2. Query the raw SQLite database directly to verify password_ro is encrypted (not plaintext)
    async with app_db.app_engine.connect() as conn:
        raw_result = await conn.execute(text("SELECT password_ro FROM Databases WHERE database_name = 'secure_db'"))
        raw_password = raw_result.scalar()
        
        # Verify it's not plaintext (should be encrypted string starting with Fernet tokens or raw bytes,
        # definitely not a normal 32-character string generated by our helper)
        assert raw_password is not None
        assert raw_password != "secret-for-encryption-test"
        
    # 3. Retrieve via SQLAlchemy ORM model to verify transparent decryption
    async with app_db.get_app_db() as db:
        result = await db.execute(select(Databases).where(Databases.database_name == "secure_db"))
        db_entry = result.scalars().first()
        assert db_entry is not None
        # Should be decrypted plaintext
        assert db_entry.password_ro == "secret-for-encryption-test"

@pytest.mark.asyncio
async def test_dynamic_data_masking(async_client: AsyncClient, mock_db_session):
    """
    Tests dynamic data masking logic:
    - Persistent admin masking rules are always applied for regular users.
    - Users can specify additional ad-hoc masking columns.
    - Admin users bypass masking rules.
    """
    _mock_session, mock_result = mock_db_session
    
    # Setup mock data for query execution
    mock_result.returns_rows = True
    mock_result.fetchmany.return_value = [
        MagicMock(_mapping={"id": 1, "email": "john@example.com", "salary": 5000, "phone": "555-1234"})
    ]
    
    app_db = app.state.context.app_db
    db_uuid = None
    new_db_id = None
    
    # 1. Register DB and setup persistent masking rules for "email" and "phone"
    async with app_db.get_app_db() as db:
        # Clear existing DB entries to prevent conflict
        await db.execute(delete(Databases).where(Databases.database_name == "mask_db"))
        await db.execute(delete(MaskingRule))
        
        new_db = Databases(
            servername="mask-server",
            database_name="mask_db",
            technology="postgresql",
            db_username="test",
            db_password="password"
        )
        db.add(new_db)
        await db.commit()
        await db.refresh(new_db)
        db_uuid = new_db.uuid
        new_db_id = new_db.id
        
        rule1 = MaskingRule(database_id=new_db.id, table_name="users", column_name="email", masking_type="default", is_active=True)
        rule2 = MaskingRule(database_id=new_db.id, table_name="users", column_name="phone", masking_type="default", is_active=True)
        db.add_all([rule1, rule2])
        await db.commit()
        
    # 2. Login as regular user and execute a query
    regular_client = AsyncClient(transport=async_client._transport, base_url="http://test")
    await create_user_and_login(regular_client, "mask_user@example.com", "mask_user")
    
    # Create UserDatabaseAssociation
    async with app_db.get_app_db() as db:
        from app_database.models import User, UserDatabaseAssociation
        user_res = await db.execute(select(User).where(User.email == "mask_user@example.com"))
        test_user = user_res.scalars().first()
        
        assoc = UserDatabaseAssociation(
            user_id=test_user.id,
            database_id=new_db_id,
            role="READER",
            is_admin=False
        )
        db.add(assoc)
        await db.commit()
        
    db_info = await app_db.get_db_info()
    app.state.context.db_provider.set_db_info(db_info)
    
    # Run query without ad-hoc masking
    exec_payload = {
        "query": "SELECT * FROM users",
        "db_uuid": db_uuid
    }
    resp = await regular_client.post("/api/execute_query", json=exec_payload)
    assert resp.status_code == 200, f"Query execution failed: {resp.text}"
    data = resp.json()["data"][0]
    
    # "email" and "phone" should be masked, "salary" should NOT be masked
    assert "john" not in data["email"]
    assert "555" not in data["phone"]
    assert data["salary"] == 5000
    
    # 3. Run query with ad-hoc masking for "salary"
    exec_payload_adhoc = {
        "query": "SELECT * FROM users",
        "db_uuid": db_uuid,
        "ad_hoc_mask_columns": ["salary"]
    }
    resp_adhoc = await regular_client.post("/api/execute_query", json=exec_payload_adhoc)
    assert resp_adhoc.status_code == 200
    data_adhoc = resp_adhoc.json()["data"][0]
    
    # "email", "phone", and "salary" should all be masked!
    assert "john" not in data_adhoc["email"]
    assert "555" not in data_adhoc["phone"]
    assert data_adhoc["salary"] != 5000
    
    # 4. Login as admin and verify they bypass all masking rules
    admin_client = AsyncClient(transport=async_client._transport, base_url="http://test")
    await create_user_and_login(admin_client, "mask_admin@example.com", "mask_admin", make_admin=True)
    
    resp_admin = await admin_client.post("/api/execute_query", json=exec_payload_adhoc)
    assert resp_admin.status_code == 200
    data_admin = resp_admin.json()["data"][0]
    
    # Admin should see raw data (unmasked)
    assert data_admin["email"] == "john@example.com"
    assert data_admin["phone"] == "555-1234"
    assert data_admin["salary"] == 5000
