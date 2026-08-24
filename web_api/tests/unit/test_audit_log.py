import json

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app_database.models import AuditLog, Base
from common.audit import log_in, log_standalone
from common.audit_actions import AuditAction, AuditTarget, STATE_CHANGING


FROZEN_ACTIONS = {
    "GRANT_DATABASE_ACCESS": "grant_database_access",
    "REVOKE_DATABASE_ACCESS": "revoke_database_access",
    "CHANGE_DATABASE_ROLE": "change_database_role",
    "USER_CREATED": "user_created",
    "USER_REGISTERED": "user_registered",
    "USER_DISABLED": "user_disabled",
    "USER_ENABLED": "user_enabled",
    "PASSWORD_CHANGED": "password_changed",
    "APPROVE_QUERY": "approve_query",
    "REJECT_QUERY": "reject_query",
    "PREVIEW_QUERY": "preview_query",
    "ADD_DATABASE": "add_database",
    "REMOVE_DATABASE": "remove_database",
    "UPDATE_MASKING_RULES": "update_masking_rules",
    "LOGIN": "login",
    "LOGIN_FAILED": "login_failed",
    "LOGOUT": "logout",
    "SESSION_REVOKED": "session_revoked",
}


def test_audit_action_values_are_immutable() -> None:
    for name, value in FROZEN_ACTIONS.items():
        assert getattr(AuditAction, name).value == value


def test_state_changing_actions_are_audit_actions() -> None:
    assert all(isinstance(action, AuditAction) for action in STATE_CHANGING)


@pytest.mark.asyncio
async def test_log_in_uses_the_callers_transaction() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        async with session_factory() as session:
            await session.begin()
            await log_in(
                session,
                action=AuditAction.UPDATE_MASKING_RULES,
                target_type=AuditTarget.DATABASE,
                target_id=7,
                details={"operation": "replace_all"},
                actor_username="admin",
            )
            assert session.in_transaction()
            await session.rollback()

        async with session_factory() as session:
            count = await session.scalar(select(func.count()).select_from(AuditLog))
            assert count == 0
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_log_in_serializes_details_on_commit() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        async with session_factory.begin() as session:
            await log_in(
                session,
                action=AuditAction.UPDATE_MASKING_RULES,
                target_type=AuditTarget.DATABASE,
                target_id=7,
                details={"operation": "replace_all"},
                actor_username="admin",
            )

        async with session_factory() as session:
            row = (await session.execute(select(AuditLog))).scalar_one()
            assert row.action == AuditAction.UPDATE_MASKING_RULES
            assert row.target_id == "7"
            assert json.loads(row.details) == {"operation": "replace_all"}
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_log_standalone_rejects_state_changing_actions() -> None:
    with pytest.raises(ValueError, match="state-changing"):
        await log_standalone(None, action=AuditAction.UPDATE_MASKING_RULES)
