"""
Integration tests for admin router and service layer.
Verifies Role-Based Access Control (RBAC), database registration, and query approval workflows.
"""
from contextlib import asynccontextmanager
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy.future import select

from app import app
from app_database.models import AuditLog, Databases, QueryData, User, Workspace
from common.audit import log_in
from common.audit_actions import AuditAction, AuditTarget
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
async def test_admin_rbac_restrictions(async_client: AsyncClient):
    """
    Tests that non-admin users are blocked from accessing administrative routes.
    """
    # 1. Login as regular user
    regular_id = await create_user_and_login(async_client, "regular@example.com", "regular")
    
    # 2. Attempt to list queries waiting for approval -> should fail with 403 Forbidden
    resp_list = await async_client.get("/api/admin/queries_to_approve")
    assert resp_list.status_code == 403
    assert "Admin access required" in resp_list.json()["detail"]
    
    # 3. Attempt to approve a query -> should fail with 403 Forbidden
    resp_approve = await async_client.post("/api/admin/approve_query/1", json={"show_results": True})
    assert resp_approve.status_code == 403
    assert "Admin access required" in resp_approve.json()["detail"]
    
    # 4. Attempt to add a database at OWNER scope -> should fail with 403 Forbidden
    db_payload = {
        "servername": "new-server",
        "database_name": "new-db",
        "tech_name": "mssql",
        "connection_mode": "ro",
        "initial_admin_user_id": regular_id,
        "username_ro": "new_ro",
        "password_ro": "not-a-real-secret",
    }
    resp_add = await async_client.post("/api/owner/databases", json=db_payload)
    assert resp_add.status_code == 403
    assert "OWNER" in resp_add.json()["detail"]


@pytest.mark.asyncio
async def test_admin_cannot_decide_own_query(async_client: AsyncClient):
    """The common approval service rejects self-approval even for an ADMIN."""
    app_db = app.state.context.app_db
    async with app_db.get_app_db() as db:
        db.add(
            Databases(
                servername="self-approval-server",
                database_name="self-approval-db",
                technology="sqlite",
            )
        )
        await db.commit()

    await create_user_and_login(
        async_client, "self-admin@example.com", "self_admin", make_admin=True
    )
    async with app_db.get_app_db() as db:
        user = (
            await db.execute(select(User).where(User.email == "self-admin@example.com"))
        ).scalar_one()
        query = QueryData(
            user_id=user.id,
            servername="self-approval-server",
            database_name="self-approval-db",
            query="DELETE FROM protected_records",
            status="waiting_for_approval",
            uuid="self-approval-query",
        )
        db.add(query)
        await db.flush()
        workspace = Workspace(name="Self approval", user_id=user.id, query_id=query.id)
        db.add(workspace)
        await db.flush()
        workspace_id = workspace.id
        await db.commit()

    response = await async_client.post(
        f"/api/admin/approve_query/{workspace_id}", json={"show_results": True}
    )
    assert response.status_code == 403
    assert response.json()["error_code"] == "APPROVAL_FORBIDDEN"

    async with app_db.get_app_db() as db:
        query = (
            await db.execute(select(QueryData).where(QueryData.uuid == "self-approval-query"))
        ).scalar_one()
        assert query.status == "waiting_for_approval"


@pytest.mark.asyncio
async def test_owner_database_registration_requires_explicit_initial_admin(async_client: AsyncClient):
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

    # 1. Login as OWNER; OWNER is intentionally not a DB ADMIN.
    owner_id = await create_user_and_login(
        async_client, "owner1@example.com", "owner1", make_owner=True
    )
    async with app_db.get_app_db() as db, db.begin():
        first_admin = User(username="first_admin", email="first_admin@example.com", is_active=True)
        first_admin.set_password("StrongPassword123!")
        db.add(first_admin)
        await db.flush()
        first_admin_id = first_admin.id
    
    # 2. Add database
    db_payload = {
        "servername": "prod-server",
        "database_name": "orders_db",
        "tech_name": "postgresql",
        "connection_mode": "ro_rw",
        "initial_admin_user_id": first_admin_id,
        "username_ro": "orders_ro",
        "password_ro": "ro-secret",
        "username_rw": "orders_rw",
        "password_rw": "rw-secret",
    }
    response = await async_client.post("/api/owner/databases", json=db_payload)
    assert response.status_code == 201
    assert response.json()["message"] == "Veritabanı kaydedildi."
    
    # Verify database entry in metadata DB
    app_db = app.state.context.app_db
    async with app_db.get_app_db() as db:
        result = await db.execute(select(Databases).where(Databases.database_name == "orders_db"))
        db_entry = result.scalars().first()
        assert db_entry is not None
        assert db_entry.servername == "prod-server"
        assert db_entry.technology == "postgresql"
        assert db_entry.username_ro == "orders_ro"
        assert db_entry.password_ro == "ro-secret"
        assert db_entry.username_rw == "orders_rw"
        assert db_entry.password_rw == "rw-secret"
        from app_database.models import UserDatabaseAssociation
        associations = (
            await db.execute(
                select(UserDatabaseAssociation).where(
                    UserDatabaseAssociation.database_id == db_entry.id
                )
            )
        ).scalars().all()
        assert [(item.user_id, item.role) for item in associations] == [(first_admin_id, "ADMIN")]
        assert all(item.user_id != owner_id for item in associations)
        audit = (
            await db.execute(
                select(AuditLog).where(AuditLog.action == AuditAction.ADD_DATABASE)
            )
        ).scalar_one()
        assert audit.client_ip == "127.0.0.1"
        
    # 3. Attempt to add duplicate database -> should fail with 400 Bad Request
    response_dup = await async_client.post("/api/owner/databases", json=db_payload)
    assert response_dup.status_code == 400
    assert response_dup.json()["error_code"] == "DATABASE_ALREADY_EXISTS"
    assert response_dup.json()["message"] == "Veritabanı zaten kayıtlı."


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

    conflict_response = await admin_client.post(
        f"/api/admin/approve_query/{workspace_id}", json=approve_payload
    )
    assert conflict_response.status_code == 409
    assert conflict_response.json()["error_code"] == "APPROVAL_CONFLICT"

    async with app_db.get_app_db() as db:
        approval_audit = (
            await db.execute(
                select(AuditLog).where(AuditLog.action == AuditAction.APPROVE_QUERY)
            )
        ).scalar_one()
        assert approval_audit.client_ip == "127.0.0.1"
    
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
    invalid_rejection = await admin_client.post(
        f"/api/admin/reject_query/{workspace_id}", json={"reason": "no"}
    )
    assert invalid_rejection.status_code == 422

    reject_response = await admin_client.post(
        f"/api/admin/reject_query/{workspace_id}",
        json={"reason": "Production table change is not approved."},
    )
    assert reject_response.status_code == 200
    
    # Verify status changed to "rejected"
    async with app_db.get_app_db() as db:
        ws = await db.get(Workspace, workspace_id)
        qdata = await db.get(QueryData, ws.query_id)
        assert qdata.status == "rejected"
        assert "Production table change is not approved." in ws.description
        assert qdata.decision_reason == "Production table change is not approved."
        assert qdata.decided_by == "admin3"
        assert qdata.decided_at is not None
        rejection_audit = (
            await db.execute(
                select(AuditLog).where(AuditLog.action == AuditAction.REJECT_QUERY)
            )
        ).scalar_one()
        assert rejection_audit.client_ip == "127.0.0.1"
        
    # Verify regular user execution remains blocked. This path really is the
    # analyzer/approval gate ("not approved for execution"), so it keeps
    # QUERY_REJECTED_BY_ANALYZER; role and access denials moved to their own
    # codes in P2-1.
    exec_response = await regular_client.post(f"/api/execute_workspace/{workspace_id}")
    assert exec_response.status_code == 400
    assert exec_response.json()["error_code"] == "QUERY_REJECTED_BY_ANALYZER"


@pytest.mark.asyncio
async def test_admin_audit_log_endpoint_validates_filters_and_authorization(
    async_client: AsyncClient,
):
    app_db = app.state.context.app_db
    async with app_db.get_app_db() as db:
        database = Databases(
            servername="audit-server",
            database_name="audit-db",
            technology="sqlite",
        )
        db.add(database)
        await db.commit()
        await db.refresh(database)
        database_id = database.id

    admin_id = await create_user_and_login(
        async_client, "audit-admin@example.com", "audit-admin", make_admin=True
    )

    async with app_db.get_app_db() as db:
        admin = await db.get(User, admin_id)
        # Both records target the database this admin actually administers, so
        # the scoping added for P1-2 keeps them visible.
        for label in ("first", "second"):
            await log_in(
                db,
                actor=admin,
                action=AuditAction.ADD_DATABASE,
                target_type=AuditTarget.DATABASE,
                target_id=database_id,
                details={"database_name": label},
                client_ip="127.0.0.1",
            )
        await db.commit()

    response = await async_client.get(
        "/api/admin/audit_log",
        params={
            "action": AuditAction.ADD_DATABASE,
            "target_type": AuditTarget.DATABASE,
            "limit": 1,
        },
    )
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["action"] == AuditAction.ADD_DATABASE
    assert response.json()[0]["target"] == f"database:{database_id}"
    assert response.json()[0]["details"] == {"database_name": "second"}

    assert (
        await async_client.get("/api/admin/audit_log", params={"action": "typo"})
    ).status_code == 400
    assert (
        await async_client.get("/api/admin/audit_log", params={"target_type": "typo"})
    ).status_code == 400
    assert (
        await async_client.get("/api/admin/audit_log", params={"limit": 0})
    ).status_code == 422

    async with AsyncClient(
        transport=async_client._transport, base_url="http://test"
    ) as regular_client:
        await create_user_and_login(
            regular_client, "audit-regular@example.com", "audit-regular"
        )
        forbidden = await regular_client.get("/api/admin/audit_log")
        assert forbidden.status_code == 403


@pytest.mark.asyncio
async def test_admin_association_and_masking_audits_capture_peer_ip(
    async_client: AsyncClient,
):
    app_db = app.state.context.app_db
    async with app_db.get_app_db() as db:
        database = Databases(
            servername="peer-ip-server",
            database_name="peer-ip-db",
            technology="sqlite",
        )
        db.add(database)
        await db.commit()
        await db.refresh(database)
        database_id = database.id

    await create_user_and_login(
        async_client, "peer-admin@example.com", "peer-admin", make_admin=True
    )
    async with AsyncClient(
        transport=async_client._transport, base_url="http://test"
    ) as target_client:
        target_user_id = await create_user_and_login(
            target_client, "peer-target@example.com", "peer-target"
        )

    association = await async_client.post(
        "/api/admin/associate_user",
        json={
            "user_id": target_user_id,
            "database_id": database_id,
            "role": "READER",
        },
    )
    assert association.status_code == 200

    masking = await async_client.post(
        f"/api/admin/databases/{database_id}/masking_rules",
        json={
            "rules": [
                {
                    "table_name": "customers",
                    "column_name": "email",
                    "masking_type": "full",
                    "is_active": True,
                }
            ]
        },
    )
    assert masking.status_code == 200

    async with app_db.get_app_db() as db:
        rows = (
            await db.execute(
                select(AuditLog).where(
                    AuditLog.action.in_(
                        [
                            AuditAction.GRANT_DATABASE_ACCESS,
                            AuditAction.UPDATE_MASKING_RULES,
                        ]
                    )
                )
            )
        ).scalars().all()
        assert {row.action for row in rows} == {
            AuditAction.GRANT_DATABASE_ACCESS,
            AuditAction.UPDATE_MASKING_RULES,
        }
        assert all(row.client_ip == "127.0.0.1" for row in rows)


# --- P1-2: audit log was not scoped to the caller's databases ---------------
#
# `admin_required` only asks whether the caller is ADMIN on *at least one*
# database. The endpoint then returned the whole AuditLog table: other
# databases' access changes, OWNER operations, and every user's login history.


@pytest.mark.asyncio
async def test_audit_log_hides_other_databases_from_a_database_admin(
    async_client: AsyncClient,
):
    app_db = app.state.context.app_db
    async with app_db.get_app_db() as db:
        mine = Databases(servername="s", database_name="mine", technology="sqlite")
        theirs = Databases(servername="s", database_name="theirs", technology="sqlite")
        db.add_all([mine, theirs])
        await db.commit()
        await db.refresh(mine)
        await db.refresh(theirs)
        mine_id, theirs_id = mine.id, theirs.id

    # make_admin=True associates the user with every database that exists at the
    # time, so the second one is registered afterwards and stays out of scope.
    admin_id = await create_user_and_login(
        async_client, "scoped-admin@example.com", "scoped-admin", make_admin=False
    )
    async with app_db.get_app_db() as db:
        from app_database.models import UserDatabaseAssociation

        user = (
            await db.execute(select(User).where(User.email == "scoped-admin@example.com"))
        ).scalars().first()
        admin_id = user.id
        db.add(
            UserDatabaseAssociation(
                user_id=admin_id, database_id=mine_id, role="ADMIN", is_admin=True
            )
        )
        await db.commit()

    async with app_db.get_app_db() as db:
        admin = await db.get(User, admin_id)
        await log_in(
            db,
            actor=admin,
            action=AuditAction.UPDATE_MASKING_RULES,
            target_type=AuditTarget.DATABASE,
            target_id=mine_id,
            details={"scope": "mine"},
        )
        await log_in(
            db,
            actor=admin,
            action=AuditAction.UPDATE_MASKING_RULES,
            target_type=AuditTarget.DATABASE,
            target_id=theirs_id,
            details={"scope": "theirs"},
        )
        await db.commit()

    rows = (await async_client.get("/api/admin/audit_log")).json()
    targets = {row["target"] for row in rows}
    assert f"database:{mine_id}" in targets
    assert f"database:{theirs_id}" not in targets


@pytest.mark.asyncio
async def test_audit_log_hides_platform_records_from_a_database_admin(
    async_client: AsyncClient,
):
    """User, session and login records belong to no single database."""
    app_db = app.state.context.app_db
    async with app_db.get_app_db() as db:
        database = Databases(servername="s", database_name="d", technology="sqlite")
        db.add(database)
        await db.commit()

    admin_id = await create_user_and_login(
        async_client, "platform-blind@example.com", "platform-blind", make_admin=True
    )
    async with app_db.get_app_db() as db:
        admin = await db.get(User, admin_id)
        await log_in(
            db,
            actor=admin,
            action=AuditAction.OWNER_GRANTED,
            target_type=AuditTarget.USER,
            target_id=admin_id,
            details={"sensitive": True},
        )
        await db.commit()

    rows = (await async_client.get("/api/admin/audit_log")).json()
    assert all(not row["target"].startswith("user:") for row in rows)


@pytest.mark.asyncio
async def test_platform_owner_sees_every_audit_record(async_client: AsyncClient):
    app_db = app.state.context.app_db
    async with app_db.get_app_db() as db:
        database = Databases(servername="s", database_name="d", technology="sqlite")
        db.add(database)
        await db.commit()

    owner_id = await create_user_and_login(
        async_client, "audit-owner@example.com", "audit-owner", make_admin=True, make_owner=True
    )
    async with app_db.get_app_db() as db:
        owner = await db.get(User, owner_id)
        await log_in(
            db,
            actor=owner,
            action=AuditAction.OWNER_GRANTED,
            target_type=AuditTarget.USER,
            target_id=owner_id,
        )
        await log_in(
            db,
            actor=owner,
            action=AuditAction.UPDATE_MASKING_RULES,
            target_type=AuditTarget.DATABASE,
            target_id=99999,  # a database the owner administers nothing on
        )
        await db.commit()

    rows = (await async_client.get("/api/admin/audit_log")).json()
    targets = {row["target"] for row in rows}
    assert f"user:{owner_id}" in targets
    assert "database:99999" in targets
