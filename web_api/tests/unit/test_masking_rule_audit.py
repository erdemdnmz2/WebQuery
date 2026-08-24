import json
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from admin.services import AdminService
from app_database.models import (
    AuditLog,
    Base,
    Databases,
    MaskingRule,
    User,
    UserDatabaseAssociation,
)
from common.audit_actions import AuditAction
from common.audit_details import MaskingRulesAuditDetails


def rule(
    table_name: str,
    column_name: str,
    masking_type: str = "default",
    is_active: bool = True,
) -> SimpleNamespace:
    return SimpleNamespace(
        table_name=table_name,
        column_name=column_name,
        masking_type=masking_type,
        is_active=is_active,
    )


def test_masking_delta_contains_only_removed_rule() -> None:
    details = MaskingRulesAuditDetails.from_rule_sets(
        [rule("users", "email"), rule("users", "phone"), rule("users", "salary")],
        [rule("users", "email"), rule("users", "phone")],
    )

    assert details.added_rules == []
    assert [item.model_dump() for item in details.removed_rules] == [
        {
            "table_name": "users",
            "column_name": "salary",
            "masking_type": "default",
            "is_active": True,
        }
    ]


def test_masking_delta_represents_a_changed_rule_as_remove_and_add() -> None:
    details = MaskingRulesAuditDetails.from_rule_sets(
        [rule("users", "email", is_active=True)],
        [rule("users", "email", is_active=False)],
    )

    assert [item.is_active for item in details.removed_rules] == [True]
    assert [item.is_active for item in details.added_rules] == [False]


def test_masking_delta_rejects_duplicate_table_column_keys() -> None:
    with pytest.raises(ValueError, match="Duplicate masking rule"):
        MaskingRulesAuditDetails.from_rule_sets(
            [], [rule("users", "email"), rule("USERS", "EMAIL")]
        )


class SessionBackedAppDatabase:
    def __init__(self, session_factory: async_sessionmaker):
        self._session_factory = session_factory

    @asynccontextmanager
    async def get_app_db(self):
        async with self._session_factory() as session:
            yield session


async def seed_masking_data(session_factory: async_sessionmaker) -> tuple[User, int]:
    async with session_factory.begin() as session:
        admin = User(username="audit-admin", email="audit-admin@example.com", password="hash")
        database = Databases(
            servername="audit-server",
            database_name="audit-db",
            technology="sqlite",
        )
        session.add_all([admin, database])
        await session.flush()
        session.add(
            UserDatabaseAssociation(
                user_id=admin.id,
                database_id=database.id,
                role="ADMIN",
                is_admin=True,
            )
        )
        session.add_all(
            [
                MaskingRule(
                    database_id=database.id,
                    table_name="users",
                    column_name="email",
                    masking_type="default",
                    is_active=True,
                ),
                MaskingRule(
                    database_id=database.id,
                    table_name="users",
                    column_name="phone",
                    masking_type="default",
                    is_active=True,
                ),
                MaskingRule(
                    database_id=database.id,
                    table_name="users",
                    column_name="salary",
                    masking_type="default",
                    is_active=True,
                ),
            ]
        )
    return admin, database.id


@pytest.mark.asyncio
async def test_save_masking_rules_writes_only_the_delta_to_audit_log() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        admin, database_id = await seed_masking_data(session_factory)
        service = AdminService(SessionBackedAppDatabase(session_factory), MagicMock())

        success = await service.save_masking_rules(
            database_id,
            [rule("users", "email"), rule("users", "phone")],
            admin,
        )

        assert success is True
        async with session_factory() as session:
            audit_row = (await session.execute(select(AuditLog))).scalar_one()
            assert audit_row.action == AuditAction.UPDATE_MASKING_RULES
            assert audit_row.target_id == str(database_id)
            assert json.loads(audit_row.details) == {
                "operation": "replace_all",
                "added_rules": [],
                "removed_rules": [
                    {
                        "table_name": "users",
                        "column_name": "salary",
                        "masking_type": "default",
                        "is_active": True,
                    }
                ],
            }
            assert [
                masking_rule.column_name
                for masking_rule in (
                    await session.execute(select(MaskingRule).order_by(MaskingRule.column_name))
                ).scalars()
            ] == ["email", "phone"]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_save_masking_rules_skips_audit_when_rule_set_is_unchanged() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        admin, database_id = await seed_masking_data(session_factory)
        service = AdminService(SessionBackedAppDatabase(session_factory), MagicMock())

        success = await service.save_masking_rules(
            database_id,
            [rule("users", "email"), rule("users", "phone"), rule("users", "salary")],
            admin,
        )

        assert success is True
        async with session_factory() as session:
            assert (await session.execute(select(AuditLog))).scalars().all() == []
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_save_masking_rules_rejects_duplicates_without_changing_data() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        admin, database_id = await seed_masking_data(session_factory)
        service = AdminService(SessionBackedAppDatabase(session_factory), MagicMock())

        success = await service.save_masking_rules(
            database_id,
            [rule("users", "email"), rule("USERS", "EMAIL")],
            admin,
        )

        assert success is False
        async with session_factory() as session:
            assert [
                masking_rule.column_name
                for masking_rule in (
                    await session.execute(select(MaskingRule).order_by(MaskingRule.column_name))
                ).scalars()
            ] == ["email", "phone", "salary"]
            assert (await session.execute(select(AuditLog))).scalars().all() == []
    finally:
        await engine.dispose()
