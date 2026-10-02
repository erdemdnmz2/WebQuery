"""SPEC-0031 AC01/03/04: real SQLCancel, rollback and safe connection reuse.

Only runs on the explicitly designated disposable CI database, never a customer
target. Temporary/UUID-named fixture objects are cleaned up after each test.
"""
import asyncio
import os
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app import app
from app_database.models import ActionLogging, Databases, User, UserDatabaseAssociation
from authentication.sessions import create_session, mint_access
from query_execution.cancellation import ExecutionRegistry, QueryCancelled, current_execution
from tests.mssql.test_mssql_migration import _validated_ci_url

pytestmark = [pytest.mark.asyncio, pytest.mark.skipif(
    not os.getenv("MSSQL_TEST_URL"), reason="requires the real MSSQL CI service",
)]


async def test_real_sqlcancel_rollback_and_connection_reuse():
    url = _validated_ci_url(os.getenv("MSSQL_TEST_URL"), os.getenv("MSSQL_CI"))
    engine = create_async_engine(url, pool_size=1, max_overflow=0)
    registry = ExecutionRegistry()
    cancel_worker = ExecutionRegistry()
    started = asyncio.Event()
    task = None
    try:
        async with engine.connect() as connection:
            await connection.execute(text("CREATE TABLE #cancel_probe (value INT NOT NULL)"))
            await connection.execute(text("INSERT INTO #cancel_probe VALUES (1)"))
            await connection.commit()
            execution_id = str(uuid4())

            async def run():
                async with registry.track(1, execution_id):
                    async with AsyncSession(bind=connection) as session:
                        try:
                            async with current_execution.get().target(session, "mssql", url):
                                await session.execute(text("UPDATE #cancel_probe SET value = 2"))
                                started.set()
                                await session.execute(text("WAITFOR DELAY '00:00:20'"))
                        except BaseException:
                            await session.rollback()
                            raise
                        else:
                            await session.commit()

            task = asyncio.create_task(run())
            try:
                await asyncio.wait_for(started.wait(), 10)
                # WAITFOR must be inside the real ODBC driver, not just queued.
                await asyncio.sleep(0.25)
                assert await cancel_worker.cancel(2, execution_id) == 0
                assert await cancel_worker.cancel(1, execution_id) == 1
                with pytest.raises(QueryCancelled):
                    await asyncio.wait_for(asyncio.shield(task), 5)
                assert await connection.scalar(text("SELECT value FROM #cancel_probe")) == 1
                assert await cancel_worker.cancel(1, execution_id) == 2
                assert await connection.scalar(text("SELECT 123")) == 123
                await connection.rollback()
            finally:
                # Drain before this exact checked-out connection can be released,
                # including when an assertion or the 5-second budget fails.
                if not task.done():
                    await registry.cancel(1, execution_id)
                    try:
                        await asyncio.wait_for(asyncio.shield(task), 25)
                    except QueryCancelled:
                        pass
        # The same one-slot pool must remain usable with no lingering signal.
        async with engine.connect() as connection:
            assert await connection.scalar(text("SELECT 456")) == 456
    finally:
        await registry.close()
        await cancel_worker.close()
        await engine.dispose()


async def test_cancel_api_rolls_back_real_target_without_server_admin_permissions(async_client):
    """The HTTP/provider path must cancel with ordinary target-tier credentials."""
    url = _validated_ci_url(os.getenv("MSSQL_TEST_URL"), os.getenv("MSSQL_CI"))
    admin_engine = create_async_engine(url)
    context = app.state.context
    suffix = uuid4().hex
    table = f"cancel_probe_{suffix}"
    login = f"cancel_runner_{suffix}"
    # Disposable fixture credential, never a deployment credential.
    password = "Cancel-CI-Test1!"
    task = None
    try:
        async with admin_engine.begin() as connection:
            await connection.execute(text(f"CREATE LOGIN [{login}] WITH PASSWORD = '{password}'"))
            await connection.execute(text(f"CREATE USER [{login}] FOR LOGIN [{login}]"))
            await connection.execute(text(f"CREATE TABLE [{table}] (id INT PRIMARY KEY, value INT NOT NULL)"))
            await connection.execute(text(f"INSERT INTO [{table}] VALUES (1, 1), (2, 1)"))
            await connection.execute(text(f"GRANT SELECT, UPDATE ON [{table}] TO [{login}]"))

        async with context.app_db.get_app_db() as session:
            user = User(username="real_cancel_runner", email="real-cancel@example.com")
            database = Databases(
                servername=f"{url.host}:{url.port or 1433}", database_name=url.database,
                technology="mssql", username_ro=login, password_ro=password,
                username_rw=login, password_rw=password,
            )
            session.add_all([user, database])
            await session.flush()
            session.add(UserDatabaseAssociation(user_id=user.id, database_id=database.id, role="ADMIN"))
            await session.commit()
            await session.refresh(user)
            await session.refresh(database)
        context.db_provider.set_db_info(await context.app_db.get_db_info())
        session_id, _ = await create_session(context.app_db, user.id, None, None)
        async_client.cookies.set("access_token", mint_access(user.id, session_id))
        db_uuid = str(database.uuid)
        async with context.db_provider.get_session(user, db_uuid) as session:
            assert await session.scalar(text("SELECT IS_SRVROLEMEMBER('sysadmin')")) == 0
            assert await session.scalar(text("SELECT IS_SRVROLEMEMBER('processadmin')")) == 0

        execution_id = str(uuid4())
        async with admin_engine.connect() as blocker:
            # Hold row 2; the application writes row 1 and then blocks on row 2.
            # Observing the uncommitted first write proves SQL actually started.
            await blocker.execute(text(f"UPDATE [{table}] WITH (ROWLOCK) SET value = 3 WHERE id = 2"))
            try:
                task = asyncio.create_task(async_client.post("/api/execute_query", json={
                    "db_uuid": db_uuid, "execution_id": execution_id,
                    "query": f"UPDATE [{table}] WITH (ROWLOCK) SET value = 2 WHERE id = 1; "
                             f"UPDATE [{table}] WITH (ROWLOCK) SET value = 2 WHERE id = 2",
                }))

                async def wait_for_uncommitted_write():
                    async with admin_engine.connect() as observer:
                        while not task.done():
                            value = await observer.scalar(text(
                                f"SELECT value FROM [{table}] WITH (NOLOCK) WHERE id = 1"
                            ))
                            if value == 2:
                                return
                            await asyncio.sleep(0.05)
                        pytest.fail(f"Query ended before blocking: {(await task).status_code}")

                await asyncio.wait_for(wait_for_uncommitted_write(), 10)
                response = await async_client.post(f"/api/query_executions/{execution_id}/cancel")
                assert response.status_code == 202
                result = await asyncio.wait_for(asyncio.shield(task), 5)
                assert result.status_code == 409
                assert result.json()["error_code"] == "QUERY_CANCELLED"
                assert (await async_client.post(f"/api/query_executions/{execution_id}/cancel")).status_code == 409
                async with context.app_db.get_app_db() as session:
                    audit = (await session.execute(select(ActionLogging))).scalar_one()
                    assert audit.ErrorMessage == "QUERY_CANCELLED"
                    assert not audit.isSuccessfull
                    assert audit.trace_id
            finally:
                await blocker.rollback()
                if task is not None and not task.done():
                    await asyncio.wait_for(asyncio.shield(task), 10)

        # Use the public execution endpoint again: rollback and pool reuse.
        result = await async_client.post("/api/execute_query", json={
            "db_uuid": db_uuid, "execution_id": str(uuid4()),
            "query": f"SELECT id, value FROM [{table}] ORDER BY id",
        })
        assert result.status_code == 200
        assert result.json()["data"] == [{"id": 1, "value": 1}, {"id": 2, "value": 1}]
    finally:
        async_client.cookies.clear()
        await context.db_provider.close_engines()
        try:
            async with admin_engine.begin() as connection:
                await connection.execute(text(f"DROP TABLE IF EXISTS [{table}]"))
                await connection.execute(text(f"IF USER_ID('{login}') IS NOT NULL DROP USER [{login}]"))
                await connection.execute(text(f"IF SUSER_ID('{login}') IS NOT NULL DROP LOGIN [{login}]"))
        finally:
            await admin_engine.dispose()
