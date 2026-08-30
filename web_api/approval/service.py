"""Transport-independent, atomic risky-query approval decisions."""

import logging
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import select, update

from app_database.app_database import AppDatabase
from app_database.models import (
    ActionLogging,
    ApprovalStatus,
    Databases,
    QueryData,
    User,
    UserDatabaseAssociation,
    Workspace,
)
from common.audit import log_in
from common.audit_actions import AuditAction, AuditTarget
from common.audit_details import QueryDecisionAuditDetails
from common.clock import db_now
from common.constants import QUERY_STATUS_WAITING_FOR_APPROVAL
from common.roles import is_admin

from .exceptions import (
    ApprovalAuthorizationError,
    ApprovalConflictError,
    ApprovalNotFoundError,
    ApprovalValidationError,
)

logger = logging.getLogger(__name__)

Decision = Literal["approve_with_results", "approve_no_results", "reject"]

_STATUS_BY_DECISION: dict[Decision, str] = {
    "approve_with_results": "approved_with_results",
    "approve_no_results": "approved",
    "reject": "rejected",
}


@dataclass(frozen=True)
class DecisionOutcome:
    workspace_id: int
    query_uuid: str
    new_status: str
    requester_user_id: int
    decided_by: str


async def decide(
    app_db: AppDatabase,
    *,
    workspace_id: int,
    decision: Decision,
    actor: User | None,
    actor_slack_id: str | None = None,
    reason: str | None = None,
    client_ip: str | None = None,
) -> DecisionOutcome:
    """Apply one risky-query decision exactly once.

    Web and Slack adapters call this function. It owns authorization, the
    conditional state transition, all dependent writes, and audit logging.
    """
    normalized_reason = (reason or "").strip()
    if decision == "reject" and len(normalized_reason) < 3:
        raise ApprovalValidationError("A rejection reason of at least 3 characters is required.")

    if actor is None:
        raise ApprovalAuthorizationError(
            "The approving Slack account is not linked to a WebQuery user."
        )

    async with app_db.get_app_db() as db:
        async with db.begin():
            workspace = (
                await db.execute(select(Workspace).where(Workspace.id == workspace_id))
            ).scalar_one_or_none()
            if workspace is None:
                raise ApprovalNotFoundError("Approval workspace was not found.")

            query_data = (
                await db.execute(
                    select(QueryData).where(QueryData.id == workspace.query_id)
                )
            ).scalar_one_or_none()
            if query_data is None:
                raise ApprovalNotFoundError("Approval query was not found.")

            database = (
                await db.execute(
                    select(Databases).where(
                        Databases.servername == query_data.servername,
                        Databases.database_name == query_data.database_name,
                    )
                )
            ).scalar_one_or_none()
            if database is None:
                raise ApprovalNotFoundError("Target database is not registered.")

            association = (
                await db.execute(
                    select(UserDatabaseAssociation).where(
                        UserDatabaseAssociation.user_id == actor.id,
                        UserDatabaseAssociation.database_id == database.id,
                    )
                )
            ).scalar_one_or_none()
            if association is None or not is_admin(association.role):
                raise ApprovalAuthorizationError(
                    "You do not have ADMIN permission for this database."
                )

            if actor.id == query_data.user_id:
                raise ApprovalAuthorizationError(
                    "You cannot approve or reject your own query."
                )

            new_status = _STATUS_BY_DECISION[decision]
            decided_at = db_now()
            result = await db.execute(
                update(QueryData)
                .where(
                    QueryData.id == query_data.id,
                    QueryData.status == QUERY_STATUS_WAITING_FOR_APPROVAL,
                )
                .values(
                    status=new_status,
                    decision_reason=normalized_reason if decision == "reject" else None,
                    decided_by=actor.username,
                    decided_at=decided_at,
                )
            )
            if result.rowcount != 1:
                current_status = (
                    await db.execute(
                        select(QueryData.status).where(QueryData.id == query_data.id)
                    )
                ).scalar_one_or_none()
                raise ApprovalConflictError(
                    f"This query has already been decided (status: {current_status})."
                )

            workspace.show_results = decision == "approve_with_results"
            if decision == "reject":
                workspace.description = (
                    f"Rejected by {actor.username}: {normalized_reason}"[:255]
                )
            else:
                workspace.description = (
                    f"Approved by {actor.username}"
                    f" ({'executable' if workspace.show_results else 'not executable'})"
                )

            await db.execute(
                update(ActionLogging)
                .where(ActionLogging.trace_id == query_data.uuid)
                .values(
                    approval_status=(
                        ApprovalStatus.REJECTED
                        if decision == "reject"
                        else ApprovalStatus.APPROVED
                    ),
                    approved_execution=workspace.show_results,
                    approved_by=actor.username,
                    approved_by_slack_id=actor_slack_id,
                    approved_at=decided_at,
                )
            )

            await log_in(
                db,
                actor=actor,
                actor_slack_id=actor_slack_id,
                action=(
                    AuditAction.REJECT_QUERY
                    if decision == "reject"
                    else AuditAction.APPROVE_QUERY
                ),
                target_type=AuditTarget.WORKSPACE,
                target_id=workspace.id,
                trace_id=str(query_data.uuid),
                details=QueryDecisionAuditDetails(
                    decision="reject" if decision == "reject" else "approve",
                    source="slack" if actor_slack_id else "web",
                    query_id=query_data.id,
                    database_id=database.id,
                    status=new_status,
                    show_results=workspace.show_results,
                    reason=normalized_reason if decision == "reject" else None,
                ),
                client_ip=client_ip,
            )

            outcome = DecisionOutcome(
                workspace_id=workspace.id,
                query_uuid=str(query_data.uuid),
                new_status=new_status,
                requester_user_id=query_data.user_id,
                decided_by=actor.username,
            )

    logger.info(
        "Approval decision completed: workspace=%s decision=%s actor=%s",
        outcome.workspace_id,
        decision,
        outcome.decided_by,
    )
    return outcome
