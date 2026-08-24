"""Transaction-aware helpers for writing ``AuditLog`` records."""
import json
import logging
from datetime import datetime
from typing import Any

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app_database.models import AuditLog
from common.audit_actions import AuditAction, AuditTarget, STATE_CHANGING

logger = logging.getLogger("web_api.audit")


def _normalize_details(details: Any) -> Any:
    if isinstance(details, BaseModel):
        return details.model_dump(mode="json")
    return details


async def log_in(
    session: AsyncSession,
    *,
    actor: Any = None,
    action: AuditAction,
    target_type: AuditTarget | None = None,
    target_id: Any = None,
    details: Any = None,
    client_ip: str | None = None,
    trace_id: str | None = None,
    actor_slack_id: str | None = None,
    actor_username: str | None = None,
) -> None:
    """Add an audit row to the caller transaction without committing it."""
    normalized_details = _normalize_details(details)
    session.add(
        AuditLog(
            created_at=datetime.now(),
            actor_user_id=getattr(actor, "id", None) if actor else None,
            actor_username=(
                actor_username
                if actor_username is not None
                else (getattr(actor, "username", None) if actor else None)
            ),
            actor_slack_id=actor_slack_id,
            action=action,
            target_type=target_type,
            target_id=str(target_id) if target_id is not None else None,
            details=(
                json.dumps(normalized_details, ensure_ascii=False, default=str)
                if normalized_details is not None
                else None
            ),
            client_ip=client_ip,
            trace_id=trace_id,
        )
    )


async def log_standalone(app_db: Any, *, action: AuditAction, **kwargs: Any) -> None:
    """Write a non-state-changing event in a separate transaction."""
    if action in STATE_CHANGING:
        raise ValueError(f"{action} is state-changing; use log_in(session, ...)")

    try:
        async with app_db.get_app_db() as db:
            async with db.begin():
                await log_in(db, action=action, **kwargs)
    except Exception:
        logger.exception("Could not write standalone audit record: action=%s", action)
