"""`UserDatabaseAssociation.is_admin` must never contradict `role` (P2-20b).

Every authorization decision in the application reads `role` through
`common.roles`. `is_admin` is a mirror that API responses and existing queries
still use, so a row where the two disagree reports a permission the application
does not actually honour - or hides one it does.
"""
from contextlib import asynccontextmanager

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app_database.models import Base, UserDatabaseAssociation


@asynccontextmanager
async def sessions():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        await engine.dispose()


async def _read_back(session_factory) -> UserDatabaseAssociation:
    async with session_factory() as session:
        return (await session.execute(select(UserDatabaseAssociation))).scalar_one()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("role", "expected"),
    [
        ("ADMIN", True),
        ("READER,ADMIN", True),
        ("READER", False),
        ("READER,WRITER,DDL", False),
    ],
)
async def test_insert_derives_the_mirror_from_the_role(role, expected):
    async with sessions() as session_factory:
        async with session_factory.begin() as session:
            session.add(UserDatabaseAssociation(user_id=1, database_id=1, role=role))

        assert (await _read_back(session_factory)).is_admin is expected


@pytest.mark.asyncio
async def test_a_wrong_mirror_passed_at_insert_is_corrected():
    """A caller that forgets to update `is_admin` cannot write a lying row."""
    async with sessions() as session_factory:
        async with session_factory.begin() as session:
            session.add(
                UserDatabaseAssociation(
                    user_id=1, database_id=1, role="READER", is_admin=True
                )
            )

        assert (await _read_back(session_factory)).is_admin is False


@pytest.mark.asyncio
async def test_a_role_change_moves_the_mirror_with_it():
    async with sessions() as session_factory:
        async with session_factory.begin() as session:
            session.add(UserDatabaseAssociation(user_id=1, database_id=1, role="ADMIN"))

        async with session_factory.begin() as session:
            row = (await session.execute(select(UserDatabaseAssociation))).scalar_one()
            # Only `role` is touched, exactly as a call site that forgot the mirror.
            row.role = "READER"

        assert (await _read_back(session_factory)).is_admin is False


@pytest.mark.asyncio
async def test_the_mirror_cannot_be_flipped_on_its_own():
    async with sessions() as session_factory:
        async with session_factory.begin() as session:
            session.add(UserDatabaseAssociation(user_id=1, database_id=1, role="READER"))

        async with session_factory.begin() as session:
            row = (await session.execute(select(UserDatabaseAssociation))).scalar_one()
            row.is_admin = True

        row = await _read_back(session_factory)
        assert row.is_admin is False
        assert row.role == "READER"
