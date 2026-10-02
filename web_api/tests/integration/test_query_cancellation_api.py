"""SPEC-0032 AC02, AC03, AC07: authenticated API, audit and legacy requests."""
import asyncio
from contextlib import asynccontextmanager
from uuid import uuid4

import pytest
from sqlalchemy import select

from app import app
from app_database.models import ActionLogging, Databases, QueryData, User, UserDatabaseAssociation, Workspace
from authentication.sessions import create_session, mint_access
from query_execution.cancellation import ExecutionRegistry, current_execution
from tests.cancellation_helpers import MemoryExecutionStore

pytestmark = pytest.mark.asyncio


async def test_cancel_requires_authentication(async_client):
    response = await async_client.post(f"/api/query_executions/{uuid4()}/cancel")
    assert response.status_code == 401


async def test_cancel_api_owner_validation_and_finished_conflict(async_client):
    registry = ExecutionRegistry(MemoryExecutionStore())
    app.state.context.execution_registry = registry
    user = User(username="caller", email="caller@example.com")
    async with app.state.context.app_db.get_app_db() as session:
        session.add(user)
        await session.commit()
        await session.refresh(user)
    session_id, _ = await create_session(app.state.context.app_db, user.id, None, None)
    async_client.cookies.set("access_token", mint_access(user.id, session_id))
    execution_id = str(uuid4())
    try:
        assert (await async_client.post("/api/query_executions/not-a-uuid/cancel")).status_code == 422
        async with registry.track(user.id + 1, execution_id):
            response = await async_client.post(f"/api/query_executions/{execution_id}/cancel")
            assert response.status_code == 404
            assert await registry.client.get(registry.key(user.id + 1, execution_id)) == "running"
        async with registry.track(user.id, execution_id):
            response = await async_client.post(f"/api/query_executions/{execution_id}/cancel")
            assert response.status_code == 202
            assert response.json() == {"status": "cancelling"}
        response = await async_client.post(f"/api/query_executions/{execution_id}/cancel")
        assert response.status_code == 409
        assert response.json()["error_code"] == "QUERY_EXECUTION_CONFLICT"
    finally:
        async_client.cookies.clear()


@pytest.mark.parametrize("surface", ["adhoc", "workspace", "preview"])
async def test_original_request_waits_for_target_end_and_audits_cancel(async_client, monkeypatch, surface):
    context = app.state.context
    registry = ExecutionRegistry(MemoryExecutionStore())
    context.execution_registry = registry
    async with context.app_db.get_app_db() as session:
        user = User(username="runner", email="runner@example.com")
        database = Databases(servername="test-server", database_name="test-db", technology="mssql")
        session.add_all([user, database])
        await session.flush()
        session.add(UserDatabaseAssociation(user_id=user.id, database_id=database.id,
                    role="ADMIN" if surface == "preview" else "READER"))
        query = QueryData(user_id=user.id, servername=database.servername,
                          database_name=database.database_name, query="SELECT 1",
                          uuid=str(uuid4()), status="approved_with_results")
        session.add(query)
        await session.flush()
        workspace = Workspace(user_id=user.id, name="Cancellation test", query_id=query.id, show_results=True)
        session.add(workspace)
        await session.commit()
        await session.refresh(user)
        await session.refresh(database)
        await session.refresh(workspace)
    context.db_provider.set_db_info(await context.app_db.get_db_info())
    session_id, _ = await create_session(context.app_db, user.id, None, None)
    async_client.cookies.set("access_token", mint_access(user.id, session_id))
    started = asyncio.Event()
    allow_driver_end = asyncio.Event()

    @asynccontextmanager
    async def blocking_target(*args, **kwargs):
        handle = current_execution.get()
        started.set()
        await allow_driver_end.wait()
        await handle.check()
        yield  # cancelled work never reaches run_statement

    monkeypatch.setattr(context.db_provider, "get_session", blocking_target)
    execution_id = str(uuid4())
    task = None
    try:
        path = {"adhoc": "/api/execute_query", "workspace": f"/api/execute_workspace/{workspace.id}",
                "preview": f"/api/admin/execute_for_preview/{workspace.id}"}[surface]
        payload = {"execution_id": execution_id}
        if surface == "adhoc":
            payload.update(query="SELECT 1", db_uuid=str(database.uuid))
        task = asyncio.create_task(async_client.post(path, json=payload))
        await asyncio.wait_for(started.wait(), 3)
        response = await async_client.post(f"/api/query_executions/{execution_id}/cancel")
        assert response.status_code == 202
        assert not task.done()  # acknowledgement is NOT completed SQL cancellation
        allow_driver_end.set()
        result = await asyncio.wait_for(task, 3)
        assert result.status_code == 409
        assert result.json()["error_code"] == "QUERY_CANCELLED"
        assert result.json()["trace_id"]
        async with context.app_db.get_app_db() as session:
            audit = (await session.execute(select(ActionLogging))).scalar_one()
            assert audit.ErrorMessage == "QUERY_CANCELLED"
            assert not audit.isSuccessfull
            if surface == "adhoc":
                assert audit.trace_id
    finally:
        allow_driver_end.set()
        if task is not None and not task.done():
            await task
        async_client.cookies.clear()
