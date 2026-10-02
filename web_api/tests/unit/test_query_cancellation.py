"""SPEC-0032 AC01–05, AC07: ownership, real driver signal and transaction seal."""
import asyncio
import threading
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

from database_provider.database import DatabaseProvider
from query_execution import cancellation as module
from query_execution.cancellation import (
    CancellationUnavailable, ExecutionConflict, ExecutionRegistry,
    QueryCancelled, current_execution,
)
from tests.cancellation_helpers import MemoryExecutionStore

pytestmark = pytest.mark.asyncio


async def test_cross_worker_ownership_duplicate_and_tombstone():
    store = MemoryExecutionStore()
    worker = ExecutionRegistry(store)
    other_worker = ExecutionRegistry(store)
    async with worker.track(1, "id"):
        assert current_execution.get() is not None
        assert await other_worker.cancel(2, "id") == 0
        async with other_worker.track(2, "id"):
            assert await other_worker.cancel(2, "id") == 1
        with pytest.raises(ExecutionConflict):
            async with other_worker.track(1, "id"):
                pass
        assert await other_worker.cancel(1, "id") == 1
        assert await other_worker.cancel(1, "id") == 1  # idempotent
        with pytest.raises(QueryCancelled):
            await current_execution.get().check()
    assert current_execution.get() is None
    assert await other_worker.cancel(1, "id") == 2


async def test_legacy_request_does_not_require_redis():
    client = AsyncMock()
    registry = ExecutionRegistry(client)
    async with registry.track(1, None):
        assert current_execution.get() is None
    client.set.assert_not_awaited()


async def test_atomic_commit_seal_rejects_late_cancel():
    registry = ExecutionRegistry(MemoryExecutionStore())
    async with registry.track(1, "id"):
        await current_execution.get().seal()
        assert await registry.cancel(1, "id") == 2


async def test_cancel_wins_before_commit_seal():
    registry = ExecutionRegistry(MemoryExecutionStore())
    async with registry.track(1, "id"):
        assert await registry.cancel(1, "id") == 1
        handle = current_execution.get()
        await handle.seal()
        assert handle.requested


async def test_redis_failure_is_service_error():
    client = AsyncMock()
    client.eval.side_effect = RedisConnectionError("never expose internal server")
    with pytest.raises(CancellationUnavailable) as error:
        await ExecutionRegistry(client).cancel(1, "id")
    assert "internal" not in error.value.message
    assert error.value.status_code == 503


async def test_cancel_before_target_does_not_connect():
    registry = ExecutionRegistry(MemoryExecutionStore())
    session = AsyncMock()
    async with registry.track(1, "id"):
        await registry.cancel(1, "id")
        with pytest.raises(QueryCancelled):
            async with current_execution.get().target(session, "mssql", "unused"):
                pytest.fail("must not execute SQL")
    session.connection.assert_not_awaited()


def bind_mock_cursor(monkeypatch, session, raw_cursor):
    listeners = {}
    monkeypatch.setattr(module.event, "listen", lambda conn, name, fn: listeners.update(fn=fn))
    removed = MagicMock()
    monkeypatch.setattr(module.event, "remove", removed)
    session.connection.return_value.sync_connection = object()

    def start_statement():
        listeners["fn"](None, SimpleNamespace(_cursor=SimpleNamespace(_impl=raw_cursor)),
                        "SELECT 1", (), None, False)
    return start_statement, removed


async def test_mssql_stops_actual_cursor_on_separate_thread_and_drains(monkeypatch):
    registry = ExecutionRegistry(MemoryExecutionStore())
    session = AsyncMock()
    loop = asyncio.get_running_loop()
    cancelled = asyncio.Event()
    thread_ids = []

    def cancel():
        thread_ids.append(threading.get_ident())
        loop.call_soon_threadsafe(cancelled.set)

    cursor = SimpleNamespace(cancel=cancel)
    start, removed = bind_mock_cursor(monkeypatch, session, cursor)
    async with registry.track(1, "id"):
        handle = current_execution.get()
        with pytest.raises(QueryCancelled):
            async with handle.target(session, "mssql", "unused"):
                start()
                await registry.cancel(1, "id")
                await asyncio.wait_for(cancelled.wait(), 2)
                raise RuntimeError("driver cancellation error")
        assert handle.cursor is None
        assert handle.stop.is_set()
        count = len(thread_ids)
        await asyncio.sleep(0.15)
        assert len(thread_ids) == count  # no signal after pool release
    assert thread_ids and all(t != threading.get_ident() for t in thread_ids)
    removed.assert_called_once()


@pytest.mark.parametrize("technology,expected", [
    ("postgresql", "SELECT pg_cancel_backend(:pid)"), ("mysql", "KILL QUERY 42"),
])
async def test_control_connection_uses_same_account_and_server_id(monkeypatch, technology, expected):
    registry = ExecutionRegistry(MemoryExecutionStore())
    session = AsyncMock()
    session.scalar.return_value = 42
    bind_mock_cursor(monkeypatch, session, None)
    stopped = asyncio.Event()
    control_connection = AsyncMock()

    async def execute(*args):
        stopped.set()

    control_connection.execute.side_effect = execute
    control = MagicMock()
    control.connect.return_value.__aenter__ = AsyncMock(return_value=control_connection)
    control.connect.return_value.__aexit__ = AsyncMock(return_value=False)
    control.dispose = AsyncMock()
    factory = MagicMock(return_value=control)
    monkeypatch.setattr(module, "create_async_engine", factory)
    async with registry.track(1, "id"):
        with pytest.raises(QueryCancelled):
            async with current_execution.get().target(session, technology, "same-tier-url"):
                await registry.cancel(1, "id")
                await asyncio.wait_for(stopped.wait(), 2)
    assert factory.call_args.args == ("same-tier-url",)
    assert factory.call_args.kwargs["isolation_level"] == "AUTOCOMMIT"
    args = control_connection.execute.call_args.args
    assert str(args[0]) == expected
    if technology == "postgresql":
        assert args[1] == {"pid": 42}
    control.dispose.assert_awaited_once()


@pytest.mark.parametrize("cancelled", [False, True])
async def test_provider_commits_only_after_seal_or_rolls_back(monkeypatch, cancelled):
    provider = DatabaseProvider()
    provider.set_db_info({"test-server": {"technology": "mssql", "databases": [
        {"name": "test-db", "uuid": "db-id"},
    ]}})
    provider.engine_cache.get_engine = AsyncMock(return_value=object())
    session = AsyncMock()
    factory = MagicMock()
    factory.return_value.__aenter__ = AsyncMock(return_value=session)
    factory.return_value.__aexit__ = AsyncMock(return_value=False)
    monkeypatch.setattr("database_provider.database.async_sessionmaker", lambda **kw: factory)
    registry = ExecutionRegistry(MemoryExecutionStore())

    @asynccontextmanager
    async def target(*args):
        yield
        assert session.commit.await_count == 0
        await current_execution.get().seal()
        if current_execution.get().requested:
            raise QueryCancelled()

    async with registry.track(1, "id"):
        monkeypatch.setattr(current_execution.get(), "target", target)
        try:
            async with provider.get_session(None, "db-id", "rw"):
                if cancelled:
                    await registry.cancel(1, "id")
        except QueryCancelled:
            assert cancelled
        else:
            assert not cancelled
    if cancelled:
        session.rollback.assert_awaited_once()
        session.commit.assert_not_awaited()
    else:
        session.commit.assert_awaited_once()
        session.rollback.assert_not_awaited()
    session.close.assert_awaited()
