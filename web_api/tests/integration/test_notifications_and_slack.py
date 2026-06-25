"""
Integration tests for Slack Interactive listener and Notification services.
Mocks out-of-band network calls and verifies database state transitions.
"""
import pytest
import httpx
from unittest.mock import MagicMock, AsyncMock, patch
from sqlalchemy.future import select
from httpx import AsyncClient

from app import app
from app_database.models import User, Workspace, QueryData
from slack_integration.listener import SlackListener
from notification.services import NotificationService

async def create_test_user_and_workspace(email: str, username: str) -> tuple[int, str]:
    """
    Helper function to create a test user and a workspace with its query data in metadata DB.
    Uses a single transaction to prevent expired attributes lazy loading issues.
    """
    app_db = app.state.app_db
    async with app_db.get_app_db() as db:
        # 1. Create and flush user to get ID
        user = User(username=username, email=email)
        user.set_password("Password123!")
        db.add(user)
        await db.flush()
        user_id = user.id
        
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
        
        return ws_id, qdata_uuid


@pytest.mark.asyncio
async def test_slack_interactive_approval_flow(async_client: AsyncClient):
    """
    Tests the Slack Bolt app approval action handler.
    Simulates a Slack admin clicking the 'Approve' button and verifies metadata DB updates.
    """
    # 1. Setup test workspace and query data
    ws_id, q_uuid = await create_test_user_and_workspace("user_slack_appr@example.com", "slack_appr_user")
    
    # 2. Instantiate SlackListener with app_db
    app_db = app.state.app_db
    listener = SlackListener(app_db=app_db)
    
    # 3. Construct mock body and respond callbacks
    mock_ack = AsyncMock()
    mock_respond = AsyncMock()
    mock_body = {
        "user": {"id": "U_ADMIN_123"},
        "actions": [{"value": q_uuid}]
    }
    
    # 4. Trigger the handler directly
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
    
    # Verify DB state was updated successfully
    async with app_db.get_app_db() as db:
        result_q = await db.execute(select(QueryData).where(QueryData.uuid == q_uuid))
        qdata = result_q.scalars().first()
        assert qdata.status == "approved_with_results"
        
        result_ws = await db.execute(select(Workspace).where(Workspace.query_id == qdata.id))
        ws = result_ws.scalars().first()
        assert ws.show_results is True
        assert "Approved by admin via Slack" in ws.description


@pytest.mark.asyncio
async def test_slack_interactive_rejection_flow(async_client: AsyncClient):
    """
    Tests the Slack Bolt app rejection action handler.
    Simulates a Slack admin clicking the 'Reject' button and verifies metadata DB updates.
    """
    # 1. Setup test workspace and query data
    ws_id, q_uuid = await create_test_user_and_workspace("user_slack_rej@example.com", "slack_rej_user")
    
    # 2. Instantiate SlackListener
    app_db = app.state.app_db
    listener = SlackListener(app_db=app_db)
    
    # 3. Construct mock body and respond callbacks
    mock_ack = AsyncMock()
    mock_respond = AsyncMock()
    mock_body = {
        "user": {"id": "U_ADMIN_999"},
        "actions": [{"value": q_uuid}]
    }
    
    # 4. Trigger the handler directly
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
