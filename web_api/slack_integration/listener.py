"""Slack adapters for the common risky-query approval decision service."""

import json
import logging
import re

from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from slack_bolt.async_app import AsyncApp
from sqlalchemy import select

from approval.service import decide
from app_database.app_database import AppDatabase
from app_database.models import QueryData, User, Workspace
from common.exceptions import BaseServiceException
from slack_integration.config import SLACK_APP_TOKEN, SLACK_BOT_TOKEN

logger = logging.getLogger(__name__)


class SlackListener:
    """Translate Slack interactions into shared approval-service calls."""

    def __init__(self, app_db: AppDatabase):
        self.app = AsyncApp(token=SLACK_BOT_TOKEN)
        self.app_db = app_db
        self.handler = None
        self.register_handlers()

    def register_handlers(self):
        @self.app.action("approve_with_results")
        async def approve(ack, body, respond):
            await self.handle_approve_with_results(ack, body, respond)

        @self.app.action("reject_query")
        async def reject(ack, body, respond):
            await self.handle_reject_query(ack, body, respond)

        @self.app.view("reject_query_reason")
        async def reject_reason_submission(ack, body, view, client):
            await self.handle_reject_reason_submission(ack, body, view, client)

    async def start(self):
        if not SLACK_APP_TOKEN:
            print("⚠️ SLACK_APP_TOKEN missing, Slack Socket Mode could not be started.")
            return
        self.handler = AsyncSocketModeHandler(self.app, SLACK_APP_TOKEN)
        await self.handler.start_async()

    async def _resolve_approver(self, slack_user_id: str) -> tuple[User, str]:
        """Validate Slack identity and require an exact WebQuery user match."""
        try:
            response = await self.app.client.users_info(user=slack_user_id)
        except Exception as exc:
            logger.error("[Slack] users_info failed for %s: %s", slack_user_id, exc)
            raise ValueError(f"Could not fetch Slack user info: {exc}") from exc

        if not response.get("ok"):
            raise ValueError(f"Slack API error: {response.get('error', 'unknown_error')}")
        slack_user = response.get("user")
        if not slack_user:
            raise ValueError("Slack API response missing user data.")
        if slack_user.get("deleted"):
            raise ValueError("Slack account has been deleted and cannot perform approvals.")
        if slack_user.get("is_bot") or slack_user.get("id") == "USLACKBOT":
            raise ValueError("Bot accounts cannot perform approvals.")
        if slack_user.get("is_restricted") or slack_user.get("is_ultra_restricted"):
            raise ValueError("Guest accounts are not permitted to approve queries.")

        email = slack_user.get("profile", {}).get("email")
        if not email:
            raise ValueError("Slack user profile does not expose an email address.")
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            raise ValueError("Slack returned an invalid email address.")

        async with self.app_db.get_app_db() as session:
            approver = (
                await session.execute(select(User).where(User.email == email))
            ).scalar_one_or_none()
        if approver is None:
            logger.warning("[Slack] No WebQuery user matches Slack account %s", slack_user_id)
            raise ValueError("Slack account is not linked to a WebQuery user.")
        return approver, slack_user_id

    async def _workspace_id_for(self, request_id: str) -> int | None:
        """Resolve Slack's query UUID to the shared service's workspace key."""
        async with self.app_db.get_app_db() as session:
            return (
                await session.execute(
                    select(Workspace.id)
                    .join(QueryData, Workspace.query_id == QueryData.id)
                    .where(QueryData.uuid == request_id)
                )
            ).scalar_one_or_none()

    async def handle_approve_with_results(self, ack, body, respond):
        """Approve only after the shared database transaction succeeds."""
        await ack()
        slack_user_id = body["user"]["id"]
        request_id = body["actions"][0]["value"]
        try:
            approver, actor_slack_id = await self._resolve_approver(slack_user_id)
            workspace_id = await self._workspace_id_for(request_id)
            if workspace_id is None:
                raise ValueError("Query workspace is not present.")
            await decide(
                self.app_db,
                workspace_id=workspace_id,
                decision="approve_with_results",
                actor=approver,
                actor_slack_id=actor_slack_id,
            )
        except ValueError as exc:
            await respond(
                replace_original=False,
                text=f"⛔ Approval blocked: {exc} (Slack ID: {slack_user_id})",
            )
            return
        except BaseServiceException as exc:
            await respond(
                replace_original=False,
                text=f"⛔ Approval blocked: {exc.message} (ID: {request_id})",
            )
            return
        except Exception:
            logger.exception("[Slack] Approval transaction failed for %s", request_id)
            await respond(
                replace_original=False,
                text=f"⛔ Query approval failed; no changes were saved. (ID: {request_id})",
            )
            return

        await respond(
            replace_original=True,
            blocks=[],
            text=f"✅ Query approved by <@{slack_user_id}>. (ID: {request_id})",
        )
        logger.info("Query %s approved by %s", request_id, approver.username)

    async def handle_reject_query(self, ack, body, respond):
        """Open a modal to collect the rejection reason before changing state."""
        await ack()
        request_id = body["actions"][0]["value"]
        trigger_id = body.get("trigger_id")
        if not trigger_id:
            await respond(
                replace_original=False,
                text=f"⛔ Rejection blocked: Slack trigger is missing. (ID: {request_id})",
            )
            return

        metadata = json.dumps(
            {
                "request_id": request_id,
                "channel_id": body.get("channel", {}).get("id"),
                "message_ts": body.get("container", {}).get("message_ts"),
            }
        )
        try:
            await self.app.client.views_open(
                trigger_id=trigger_id,
                view={
                    "type": "modal",
                    "callback_id": "reject_query_reason",
                    "private_metadata": metadata,
                    "title": {"type": "plain_text", "text": "Sorguyu reddet"},
                    "submit": {"type": "plain_text", "text": "Reddet"},
                    "close": {"type": "plain_text", "text": "Vazgeç"},
                    "blocks": [
                        {
                            "type": "input",
                            "block_id": "reason_block",
                            "label": {"type": "plain_text", "text": "Red gerekçesi"},
                            "element": {
                                "type": "plain_text_input",
                                "action_id": "reason_input",
                                "multiline": True,
                                "min_length": 3,
                                "max_length": 500,
                            },
                        }
                    ],
                },
            )
        except Exception:
            logger.exception("[Slack] Unable to open rejection modal for %s", request_id)
            await respond(
                replace_original=False,
                text=f"⛔ Rejection form could not be opened. (ID: {request_id})",
            )

    async def handle_reject_reason_submission(self, ack, body, view, client):
        """Persist a Slack rejection only after a valid reason is submitted."""
        metadata = json.loads(view.get("private_metadata") or "{}")
        request_id = metadata.get("request_id")
        reason = (
            view.get("state", {})
            .get("values", {})
            .get("reason_block", {})
            .get("reason_input", {})
            .get("value", "")
        )
        if not request_id:
            await ack(
                response_action="errors",
                errors={"reason_block": "Approval request is missing."},
            )
            return

        try:
            approver, actor_slack_id = await self._resolve_approver(body["user"]["id"])
            workspace_id = await self._workspace_id_for(request_id)
            if workspace_id is None:
                raise ValueError("Query workspace is not present.")
            await decide(
                self.app_db,
                workspace_id=workspace_id,
                decision="reject",
                actor=approver,
                actor_slack_id=actor_slack_id,
                reason=reason,
            )
        except (ValueError, BaseServiceException) as exc:
            message = exc.message if isinstance(exc, BaseServiceException) else str(exc)
            await ack(response_action="errors", errors={"reason_block": message})
            return
        except Exception:
            logger.exception("[Slack] Rejection transaction failed for %s", request_id)
            await ack(
                response_action="errors",
                errors={"reason_block": "Query rejection failed; no changes were saved."},
            )
            return

        await ack()
        channel_id = metadata.get("channel_id")
        message_ts = metadata.get("message_ts")
        if channel_id and message_ts:
            await client.chat_update(
                channel=channel_id,
                ts=message_ts,
                text=f"❌ Query rejected by <@{actor_slack_id}>. (ID: {request_id})",
                blocks=[],
            )
        logger.info("Query %s rejected by %s", request_id, approver.username)
