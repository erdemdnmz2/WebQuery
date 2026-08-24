"""
Slack Listener
Handles interactive button actions from Slack (approve/reject).
On approval or rejection, resolves the WebQuery user via Slack email lookup
and updates the ActionLogging audit record accordingly.
"""

import logging

from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from slack_bolt.async_app import AsyncApp
from sqlalchemy import select

from app_database.app_database import AppDatabase
from app_database.models import ApprovalStatus, Databases, QueryData, User, Workspace
from common.audit import log_in
from common.audit_actions import AuditAction, AuditTarget
from common.audit_details import QueryDecisionAuditDetails
from slack_integration.config import SLACK_APP_TOKEN, SLACK_BOT_TOKEN

logger = logging.getLogger(__name__)


class SlackListener:
    """
    Slack interactive action listener.
    Listens for approve/reject button clicks sent via Slack block-kit messages
    and persists the decision to the application database.
    """

    def __init__(self, app_db: AppDatabase):
        """
        Initializes the SlackListener with the application database.

        Args:
            app_db: The application database manager used to persist approval decisions.
        """
        self.app = AsyncApp(token=SLACK_BOT_TOKEN)
        self.app_db = app_db
        self.handler = None
        self.register_handlers()

    def register_handlers(self):
        """
        Registers Slack action handlers for 'approve_with_results' and 'reject_query' button events.
        """
        @self.app.action("approve_with_results")
        async def approve(ack, body, respond):
            await self.handle_approve_with_results(ack, body, respond)

        @self.app.action("reject_query")
        async def reject(ack, body, respond):
            await self.handle_reject_query(ack, body, respond)

    async def start(self):
        """
        Starts the Slack Socket Mode handler.
        If SLACK_APP_TOKEN is not set, the listener is skipped without raising an error.
        """
        if not SLACK_APP_TOKEN:
            print("⚠️ SLACK_APP_TOKEN missing, Slack Socket Mode could not be started.")
            return
            
        self.handler = AsyncSocketModeHandler(self.app, SLACK_APP_TOKEN)
        await self.handler.start_async()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _resolve_approver(self, slack_user_id: str) -> tuple[str | None, str]:
        """
        Resolves the WebQuery username for the Slack user who clicked the button.

        Validates the users_info API response before trusting any data:
          - Checks response ok flag
          - Rejects deleted, bot, and restricted accounts
          - Validates email presence and format

        Returns:
            tuple[str | None, str]:
                - approved_by: WebQuery username, Slack email fallback, or None if validation fails.
                - slack_user_id: The immutable Slack user ID (always returned as-is).

        Raises:
            ValueError: If the Slack user cannot be validated (deleted, bot, no email, etc.).
        """
        import re

        # --- Step 1: Call Slack users.info API ---
        try:
            response = await self.app.client.users_info(user=slack_user_id)
        except Exception as e:
            logger.error(f"[Slack] users_info API call failed for {slack_user_id}: {e}")
            raise ValueError(f"Could not fetch Slack user info: {e}")

        # --- Step 2: Validate API response ok flag ---
        if not response.get("ok"):
            error = response.get("error", "unknown_error")
            logger.error(f"[Slack] users_info returned ok=False for {slack_user_id}: error={error}")
            raise ValueError(f"Slack API error: {error}")

        user = response.get("user")
        if not user:
            logger.error(f"[Slack] users_info response missing 'user' field for {slack_user_id}")
            raise ValueError("Slack API response missing user data.")

        # --- Step 3: Reject deleted accounts ---
        if user.get("deleted", False):
            logger.warning(f"[Slack] Blocked approval from deleted Slack account: {slack_user_id}")
            raise ValueError("Slack account has been deleted and cannot perform approvals.")

        # --- Step 4: Reject bot accounts ---
        if user.get("is_bot", False) or user.get("id") == "USLACKBOT":
            logger.warning(f"[Slack] Blocked approval from bot account: {slack_user_id}")
            raise ValueError("Bot accounts cannot perform approvals.")

        # --- Step 5: Reject restricted/ultra-restricted (guest) accounts ---
        if user.get("is_restricted") or user.get("is_ultra_restricted"):
            logger.warning(f"[Slack] Blocked approval from restricted guest account: {slack_user_id}")
            raise ValueError("Guest accounts are not permitted to approve queries.")

        # --- Step 6: Extract and validate email ---
        profile = user.get("profile", {})
        slack_email: str | None = profile.get("email")

        if not slack_email:
            logger.warning(
                f"[Slack] No email in profile for {slack_user_id}. "
                "Ensure 'users:read.email' scope is granted and workspace policy allows email access."
            )
            raise ValueError(
                "Slack user profile does not expose an email address. "
                "Check that the 'users:read.email' OAuth scope is enabled."
            )

        email_pattern = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
        if not email_pattern.match(slack_email):
            logger.error(f"[Slack] Invalid email format from Slack for {slack_user_id}: '{slack_email}'")
            raise ValueError(f"Invalid email format returned by Slack: '{slack_email}'")

        # --- Step 7: Match to WebQuery user ---
        try:
            async with self.app_db.get_app_db() as session:
                result = await session.execute(
                    select(User).where(User.email == slack_email)
                )
                wq_user = result.scalars().first()
                if wq_user:
                    logger.info(
                        f"[Slack] Resolved approver: Slack {slack_user_id} → "
                        f"email={slack_email} → WebQuery user '{wq_user.username}'"
                    )
                    return wq_user.username, slack_user_id
        except Exception as e:
            logger.warning(f"[Slack] DB lookup failed for email {slack_email}: {e}")

        # Fallback: email validated but no matching WebQuery user found
        logger.warning(
            f"[Slack] No WebQuery user matched email '{slack_email}' (Slack ID: {slack_user_id}). "
            "Using email as fallback identifier."
        )
        return slack_email, slack_user_id

    async def _persist_query_decision(
        self,
        *,
        request_id: str,
        approved_by: str,
        approved_by_slack_id: str,
        approve: bool,
    ) -> bool:
        """Commit query state, workspace state, and audit as one transaction."""
        action = AuditAction.APPROVE_QUERY if approve else AuditAction.REJECT_QUERY
        status = "approved_with_results" if approve else "rejected"
        decision = "approve" if approve else "reject"

        try:
            async with self.app_db.get_app_db() as session, session.begin():
                query_data = (
                    await session.execute(
                        select(QueryData).where(QueryData.uuid == request_id)
                    )
                ).scalar_one_or_none()
                if query_data is None:
                    raise ValueError("Query is not present in the metadata database")

                database = (
                    await session.execute(
                        select(Databases).where(
                            Databases.servername == query_data.servername,
                            Databases.database_name == query_data.database_name,
                        )
                    )
                ).scalar_one_or_none()
                if database is None:
                    raise ValueError("Query database is not registered")

                workspace = (
                    await session.execute(
                        select(Workspace).where(Workspace.query_id == query_data.id)
                    )
                ).scalar_one_or_none()
                if workspace is None:
                    raise ValueError("Query workspace is not present")

                query_data.status = status
                workspace.show_results = approve
                workspace.description = (
                    f"Approved by {approved_by} via Slack"
                    if approve
                    else f"Rejected by {approved_by} via Slack"
                )

                await log_in(
                    session,
                    actor_username=approved_by,
                    actor_slack_id=approved_by_slack_id,
                    action=action,
                    target_type=AuditTarget.QUERY,
                    target_id=query_data.id,
                    trace_id=request_id,
                    details=QueryDecisionAuditDetails(
                        decision=decision,
                        source="slack",
                        query_id=query_data.id,
                        database_id=database.id,
                        status=status,
                        show_results=True if approve else None,
                    ),
                )
        except Exception:
            logger.exception("[Slack] Decision transaction failed for %s", request_id)
            return False

        return True


    # ------------------------------------------------------------------
    # Action handlers
    # ------------------------------------------------------------------

    async def handle_approve_with_results(self, ack, body, respond):
        """
        Handles the 'approve_with_results' Slack button action.
        Validates and resolves the approver, updates QueryData and Workspace records
        to 'approved_with_results', and writes the approval to the ActionLogging audit trail.

        Args:
            ack: Slack acknowledgement callback (must be called immediately).
            body: The full Slack action payload containing user and action data.
            respond: Slack response callback to update the original message.
        """
        await ack()
        slack_user_id: str = body["user"]["id"]
        request_id: str = body["actions"][0]["value"]

        # --- Resolve and validate the approver before doing anything ---
        try:
            approved_by, approved_by_slack_id = await self._resolve_approver(slack_user_id)
        except ValueError as e:
            logger.error(f"[Slack] Approval blocked for request {request_id}: {e}")
            await respond(
                replace_original=False,
                text=f"⛔ Approval blocked: {e} (Slack ID: {slack_user_id})"
            )
            return

        persisted = await self._persist_query_decision(
            request_id=request_id,
            approved_by=approved_by,
            approved_by_slack_id=approved_by_slack_id,
            approve=True,
        )
        if not persisted:
            await respond(
                replace_original=False,
                text=(
                    "⛔ Query approval failed; no changes were saved. "
                    f"(ID: {request_id})"
                ),
            )
            return

        await respond(
            replace_original=True,
            blocks=[],
            text=f"✅ Query approved by <@{slack_user_id}>. (ID: {request_id})",
        )
        logger.info(
            "Query %s approved by %s (Slack ID: %s)",
            request_id,
            approved_by,
            slack_user_id,
        )

        # Update ActionLogging audit record
        try:
            updated = await self.app_db.update_approval_status(
                trace_id=request_id,
                approval_status=ApprovalStatus.APPROVED,
                approved_by=approved_by,
                approved_by_slack_id=approved_by_slack_id,
            )
            if not updated:
                logger.warning(f"[Slack] No ActionLogging record found with trace_id={request_id}")
        except Exception as e:
            logger.error(f"[Slack] ActionLogging update failed for trace_id={request_id}: {e}")

    async def handle_reject_query(self, ack, body, respond):
        """
        Handles the 'reject_query' Slack button action.
        Validates and resolves the rejector, updates QueryData and Workspace records
        to 'rejected', and writes the rejection to the ActionLogging audit trail.

        Args:
            ack: Slack acknowledgement callback (must be called immediately).
            body: The full Slack action payload containing user and action data.
            respond: Slack response callback to update the original message.
        """
        await ack()
        slack_user_id: str = body["user"]["id"]
        request_id: str = body["actions"][0]["value"]

        # --- Resolve and validate the rejecter before doing anything ---
        try:
            approved_by, approved_by_slack_id = await self._resolve_approver(slack_user_id)
        except ValueError as e:
            logger.error(f"[Slack] Rejection blocked for request {request_id}: {e}")
            await respond(
                replace_original=False,
                text=f"⛔ Rejection blocked: {e} (Slack ID: {slack_user_id})"
            )
            return

        persisted = await self._persist_query_decision(
            request_id=request_id,
            approved_by=approved_by,
            approved_by_slack_id=approved_by_slack_id,
            approve=False,
        )
        if not persisted:
            await respond(
                replace_original=False,
                text=(
                    "⛔ Query rejection failed; no changes were saved. "
                    f"(ID: {request_id})"
                ),
            )
            return

        await respond(
            replace_original=True,
            blocks=[],
            text=f"❌ Query rejected by <@{slack_user_id}>. (ID: {request_id})",
        )
        logger.info(
            "Query %s rejected by %s (Slack ID: %s)",
            request_id,
            approved_by,
            slack_user_id,
        )

        # Update ActionLogging audit record
        try:
            updated = await self.app_db.update_approval_status(
                trace_id=request_id,
                approval_status=ApprovalStatus.REJECTED,
                approved_by=approved_by,
                approved_by_slack_id=approved_by_slack_id,
            )
            if not updated:
                logger.warning(f"[Slack] No ActionLogging record found with trace_id={request_id}")
        except Exception as e:
            logger.error(f"[Slack] ActionLogging update failed for trace_id={request_id}: {e}")
