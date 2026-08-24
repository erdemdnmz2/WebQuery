"""
Integration tests for Slack Interactive listener and Notification services.
Mocks out-of-band network calls and verifies database state transitions.
"""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy.future import select

from app import app
from app_database.models import AuditLog, Databases, QueryData, User, Workspace
from common.audit_actions import AuditAction
from notification.services import NotificationService
from slack_integration.listener import SlackListener


def _fake_users_info_response(email: str) -> dict:
    """
    Stand-in for a real `users_info` Slack API response — this module's own
    docstring says out-of-band network calls are mocked, but this specific
    call (slack_integration/listener.py: `self.app.client.users_info`) was
    not, so tests only passed where slack.com happened to be reachable and
    SLACK_BOT_TOKEN happened to be set (e.g. a dev machine with a real
    .env), and failed for different reasons everywhere else — SSL/network
    failure locally without one, BoltError in CI without one at all.
    """
    return {
        "ok": True,
        "user": {
            "deleted": False,
            "is_bot": False,
            "is_restricted": False,
            "is_ultra_restricted": False,
            "profile": {"email": email},
        },
    }


async def create_admin_user(email: str, username: str = "admin") -> None:
    """
    Creates a bare WebQuery user for `_resolve_approver` (listener.py) to
    match by email — this is who the mocked Slack account "is", distinct
    from the requester created by create_test_user_and_workspace.
    """
    app_db = app.state.context.app_db
    async with app_db.get_app_db() as db:
        admin = User(username=username, email=email)
        admin.set_password("Password123!")
        db.add(admin)
        await db.commit()


async def create_test_user_and_workspace(email: str, username: str) -> tuple[int, str, int]:
    """
    Helper function to create a test user and a workspace with its query data in metadata DB.
    Uses a single transaction to prevent expired attributes lazy loading issues.
    """
    app_db = app.state.context.app_db
    async with app_db.get_app_db() as db:
        # 1. Create and flush user to get ID
        user = User(username=username, email=email)
        user.set_password("Password123!")
        db.add(user)
        await db.flush()
        user_id = user.id
        
        database = Databases(
            servername="prod-server",
            database_name="finance_db",
            technology="mssql",
        )
        db.add(database)
        await db.flush()
        database_id = database.id

        # 2. Create and flush query data to get ID
        qdata = QueryData(
            query="SELECT * FROM confidential_data",
            servername="prod-server",
            database_name="finance_db",
            status="waiting_for_approval",
            uuid="test-uuid-12345",
            user_id=user_id
        )
        db.add(qdata)
        await db.flush()
        qdata_id = qdata.id
        qdata_uuid = qdata.uuid
        
        # 3. Create workspace
        ws = Workspace(
            name="Financials",
            user_id=user_id,
            query_id=qdata_id,
            show_results=False,
            description="Waiting for admin review"
        )
        db.add(ws)
        await db.flush()
        ws_id = ws.id
        await db.commit()
        
        return ws_id, qdata_uuid, database_id


@pytest.mark.asyncio
async def test_slack_interactive_approval_flow(async_client: AsyncClient):
    """
    Tests the Slack Bolt app approval action handler.
    Simulates a Slack admin clicking the 'Approve' button and verifies metadata DB updates.
    """
    # 1. Setup test workspace and query data, plus the WebQuery user the
    # mocked Slack account resolves to.
    _ws_id, q_uuid, database_id = await create_test_user_and_workspace(
        "user_slack_appr@example.com", "slack_appr_user"
    )
    await create_admin_user("admin@example.com", "admin")

    # 2. Instantiate SlackListener with app_db
    app_db = app.state.context.app_db
    listener = SlackListener(app_db=app_db)

    # 3. Construct mock body and respond callbacks
    mock_ack = AsyncMock()
    state_observed_when_responding: list[tuple[str, int]] = []

    async def capture_response_state(**_kwargs):
        async with app_db.get_app_db() as db:
            query = (
                await db.execute(select(QueryData).where(QueryData.uuid == q_uuid))
            ).scalar_one()
            audit_count = len(
                (
                    await db.execute(
                        select(AuditLog).where(
                            AuditLog.action == AuditAction.APPROVE_QUERY
                        )
                    )
                ).scalars().all()
            )
            state_observed_when_responding.append((query.status, audit_count))

    mock_respond = AsyncMock(side_effect=capture_response_state)
    mock_body = {
        "user": {"id": "U_ADMIN_123"},
        "actions": [{"value": q_uuid}]
    }

    # 4. Trigger the handler directly
    with patch.object(
        listener.app.client, "users_info",
        new=AsyncMock(return_value=_fake_users_info_response("admin@example.com")),
    ):
        await listener.handle_approve_with_results(
            ack=mock_ack,
            body=mock_body,
            respond=mock_respond
        )
    
    # Verify ack was called
    mock_ack.assert_called_once()
    
    # Verify Slack response was sent
    mock_respond.assert_called_once()
    respond_args = mock_respond.call_args[1]
    assert "Query approved" in respond_args["text"]
    assert "U_ADMIN_123" in respond_args["text"]
    assert state_observed_when_responding == [("approved_with_results", 1)]
    
    # Verify DB state was updated successfully
    async with app_db.get_app_db() as db:
        result_q = await db.execute(select(QueryData).where(QueryData.uuid == q_uuid))
        qdata = result_q.scalars().first()
        assert qdata.status == "approved_with_results"
        
        result_ws = await db.execute(select(Workspace).where(Workspace.query_id == qdata.id))
        ws = result_ws.scalars().first()
        assert ws.show_results is True
        assert "Approved by admin via Slack" in ws.description

        audit = (
            await db.execute(
                select(AuditLog).where(AuditLog.action == AuditAction.APPROVE_QUERY)
            )
        ).scalar_one()
        assert json.loads(audit.details)["database_id"] == database_id


@pytest.mark.asyncio
async def test_slack_interactive_rejection_flow(async_client: AsyncClient):
    """
    Tests the Slack Bolt app rejection action handler.
    Simulates a Slack admin clicking the 'Reject' button and verifies metadata DB updates.
    """
    # 1. Setup test workspace and query data, plus the WebQuery user the
    # mocked Slack account resolves to.
    _ws_id, q_uuid, database_id = await create_test_user_and_workspace(
        "user_slack_rej@example.com", "slack_rej_user"
    )
    await create_admin_user("admin@example.com", "admin")

    # 2. Instantiate SlackListener
    app_db = app.state.context.app_db
    listener = SlackListener(app_db=app_db)

    # 3. Construct mock body and respond callbacks
    mock_ack = AsyncMock()
    mock_respond = AsyncMock()
    mock_body = {
        "user": {"id": "U_ADMIN_999"},
        "actions": [{"value": q_uuid}]
    }

    # 4. Trigger the handler directly
    with patch.object(
        listener.app.client, "users_info",
        new=AsyncMock(return_value=_fake_users_info_response("admin@example.com")),
    ):
        await listener.handle_reject_query(
            ack=mock_ack,
            body=mock_body,
            respond=mock_respond
        )
    
    # Verify ack was called
    mock_ack.assert_called_once()
    
    # Verify Slack response was sent
    mock_respond.assert_called_once()
    respond_args = mock_respond.call_args[1]
    assert "Query rejected" in respond_args["text"]
    assert "U_ADMIN_999" in respond_args["text"]
    
    # Verify DB state was updated successfully
    async with app_db.get_app_db() as db:
        result_q = await db.execute(select(QueryData).where(QueryData.uuid == q_uuid))
        qdata = result_q.scalars().first()
        assert qdata.status == "rejected"
        
        result_ws = await db.execute(select(Workspace).where(Workspace.query_id == qdata.id))
        ws = result_ws.scalars().first()
        assert ws.show_results is False
        assert "Rejected by admin via Slack" in ws.description

        audit = (
            await db.execute(
                select(AuditLog).where(AuditLog.action == AuditAction.REJECT_QUERY)
            )
        ).scalar_one()
        assert json.loads(audit.details)["database_id"] == database_id


@pytest.mark.asyncio
async def test_slack_approval_rolls_back_when_database_is_not_registered(
    async_client: AsyncClient,
):
    _ws_id, q_uuid, database_id = await create_test_user_and_workspace(
        "user_slack_missing_db@example.com", "slack_missing_db_user"
    )
    await create_admin_user("admin@example.com", "admin")

    app_db = app.state.context.app_db
    async with app_db.get_app_db() as db:
        database = await db.get(Databases, database_id)
        await db.delete(database)
        await db.commit()

    listener = SlackListener(app_db=app_db)
    mock_ack = AsyncMock()
    mock_respond = AsyncMock()
    mock_body = {
        "user": {"id": "U_ADMIN_MISSING_DB"},
        "actions": [{"value": q_uuid}],
    }

    with patch.object(
        listener.app.client,
        "users_info",
        new=AsyncMock(return_value=_fake_users_info_response("admin@example.com")),
    ):
        await listener.handle_approve_with_results(
            ack=mock_ack,
            body=mock_body,
            respond=mock_respond,
        )

    mock_ack.assert_called_once()
    mock_respond.assert_called_once()
    assert "failed" in mock_respond.call_args.kwargs["text"].lower()

    async with app_db.get_app_db() as db:
        query = (
            await db.execute(select(QueryData).where(QueryData.uuid == q_uuid))
        ).scalar_one()
        assert query.status == "waiting_for_approval"
        assert (
            await db.execute(
                select(AuditLog).where(AuditLog.action == AuditAction.APPROVE_QUERY)
            )
        ).scalars().all() == []


@pytest.mark.asyncio
async def test_notification_webhook_payload():
    """
    Tests the NotificationService to ensure it formats and sends webhook payloads correctly.
    """
    # 1. Instantiate NotificationService with a mock Slack Webhook URL
    notifier = NotificationService()
    notifier.slack_url = "https://hooks.slack.com/services/T_MOCK/B_MOCK/W_MOCK"
    
    # 2. Mock httpx.AsyncClient.post
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        
        # 3. Send notification
        success = await notifier.send_approval_notification(
            request_id="test-req-id-777",
            username="analyst_bob",
            request_time="2026-06-25 12:00:00",
            database_name="customer_db",
            servername="prod-db-1",
            risk_type="risky_dml",
            query="DELETE FROM customers"
        )
        
        assert success is True
        
        # Verify post call
        mock_post.assert_called_once()
        post_args = mock_post.call_args
        url = post_args[0][0]
        json_payload = post_args[1]["json"]
        
        assert url == "https://hooks.slack.com/services/T_MOCK/B_MOCK/W_MOCK"
        assert "blocks" in json_payload
        
        # Verify payload contains critical query metadata
        blocks_str = str(json_payload["blocks"])
        assert "test-req-id-777" in blocks_str
        assert "analyst_bob" in blocks_str
        assert "prod-db-1" in blocks_str
        assert "customer_db" in blocks_str
        assert "DELETE FROM customers" in blocks_str
