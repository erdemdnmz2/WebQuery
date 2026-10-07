"""Owner-scoped, cross-worker cancellation of a target database statement.

Never cancels the request task: aioodbc runs SQL in a thread, and cancelling
that task would leave SQL running while returning its connection to the pool.
"""
import asyncio
import logging
import os
from contextlib import asynccontextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field

from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from common.exceptions import BaseServiceException
from database_provider.config import QUERY_TIMEOUT_SECONDS, get_connect_args

logger = logging.getLogger(__name__)


class QueryCancelled(BaseServiceException):
    status_code = 409
    code = "QUERY_CANCELLED"

    def __init__(self):
        super().__init__("Sorgu hedef veritabanında iptal edildi.")


class CancellationUnavailable(BaseServiceException):
    status_code = 503
    code = "QUERY_CANCELLATION_UNAVAILABLE"

    def __init__(self):
        super().__init__("Sorgu iptal hizmetine ulaşılamıyor. Tekrar deneyin.")


class ExecutionConflict(BaseServiceException):
    status_code = 409
    code = "QUERY_EXECUTION_CONFLICT"


_CANCEL = """
local state = redis.call('GET', KEYS[1])
if not state then return 0 end
if state == 'sealed' then return 2 end
redis.call('SET', KEYS[1], 'cancelling', 'KEEPTTL')
return 1
"""
_SEAL = """
local state = redis.call('GET', KEYS[1])
if not state then return -1 end
redis.call('SET', KEYS[1], 'sealed', 'KEEPTTL')
if state == 'cancelling' then return 1 end
return 0
"""


class ExecutionRegistry:
    def __init__(self, client=None):
        self.client = client if client is not None else Redis.from_url(
            os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
            decode_responses=True, socket_connect_timeout=2, socket_timeout=2,
        )
        self.ttl = max(600, QUERY_TIMEOUT_SECONDS + 120)

    @staticmethod
    def key(user_id: int, execution_id: str) -> str:
        return f"webquery:execution:{user_id}:{execution_id}"

    async def _call(self, method, *args, **kwargs):
        try:
            return await method(*args, **kwargs)
        except RedisError as exc:
            raise CancellationUnavailable() from exc

    async def cancel(self, user_id: int, execution_id: str) -> int:
        return int(await self._call(self.client.eval, _CANCEL, 1, self.key(user_id, execution_id)))

    @asynccontextmanager
    async def track(self, user_id: int, execution_id: str | None):
        if execution_id is None:
            yield
            return
        key = self.key(user_id, execution_id)
        if not await self._call(self.client.set, key, "running", nx=True, ex=self.ttl):
            raise ExecutionConflict("Bu çalıştırma kimliği zaten kullanılıyor.")
        handle = TargetExecution(self, key)
        token = current_execution.set(handle)
        try:
            yield
        finally:
            current_execution.reset(token)
            # A short tombstone prevents a late cancellation or auth retry from
            # reusing an execution ID. No SQL or credentials live in Redis.
            try:
                await self._call(self.client.set, key, "sealed", ex=30)
            except CancellationUnavailable:
                logger.warning("Sorgu iptal kaydı temizlenemedi; TTL ile silinecek")

    async def close(self):
        await self.client.aclose()


@dataclass
class TargetExecution:
    registry: ExecutionRegistry
    key: str
    requested: bool = False
    stop: asyncio.Event = field(default_factory=asyncio.Event)
    cursor: object | None = None

    async def check(self):
        state = await self.registry._call(self.registry.client.get, self.key)
        if state is None:
            raise CancellationUnavailable()
        if state == "cancelling":
            self.requested = True
        if self.requested:
            raise QueryCancelled()

    async def seal(self):
        result = int(await self.registry._call(self.registry.client.eval, _SEAL, 1, self.key))
        if result == -1:
            raise CancellationUnavailable()
        self.requested |= result == 1

    @asynccontextmanager
    async def target(self, session, technology: str, connection_url: str):
        """Bind only a checked-out target session, through rollback/commit seal."""
        await self.check()
        technology = technology.lower().strip()
        connection = await session.connection()
        sync_connection = connection.sync_connection
        pid = None

        def capture_cursor(_conn, cursor, _statement, _parameters, _context, _many):
            if self.requested:
                raise QueryCancelled()
            if technology == "mssql":
                # SQLAlchemy aioodbc adapter -> aioodbc Cursor -> pyodbc Cursor.
                self.cursor = cursor._cursor._impl

        if technology in {"postgresql", "postgres"}:
            pid = int(await session.scalar(text("SELECT pg_backend_pid()")))
        elif technology == "mysql":
            pid = int(await session.scalar(text("SELECT CONNECTION_ID()")))
        elif technology != "mssql":
            raise CancellationUnavailable()

        event.listen(sync_connection, "before_cursor_execute", capture_cursor)

        async def cancel_driver():
            if technology == "mssql":
                cursor = self.cursor
                if cursor is not None:
                    # A dedicated thread avoids queueing cancellation behind
                    # the very aioodbc queries occupying the default executor.
                    from concurrent.futures import ThreadPoolExecutor
                    with ThreadPoolExecutor(max_workers=1) as executor:
                        await asyncio.get_running_loop().run_in_executor(executor, cursor.cancel)
                return
            control = create_async_engine(
                connection_url, poolclass=NullPool,
                connect_args=get_connect_args(technology, 10),
                isolation_level="AUTOCOMMIT",
            )
            try:
                async with control.connect() as control_connection:
                    if technology in {"postgresql", "postgres"}:
                        await control_connection.execute(text("SELECT pg_cancel_backend(:pid)"), {"pid": pid})
                    else:
                        # pid is obtained from this exact held connection,
                        # converted to int, never supplied by the HTTP client.
                        await control_connection.execute(text(f"KILL QUERY {pid:d}"))
            finally:
                await control.dispose()

        async def watch():
            while not self.stop.is_set():
                state = await self.registry._call(self.registry.client.get, self.key)
                if state is None:
                    raise CancellationUnavailable()
                if state == "cancelling":
                    self.requested = True
                    try:
                        await cancel_driver()
                    except Exception as exc:
                        # Don't report completion here. The original SQL must
                        # end and rollback before QUERY_CANCELLED is returned.
                        logger.warning("Hedef iptal sinyali başarısız: %s", type(exc).__name__)
                    # A signal may arrive just before the driver actually
                    # starts SQL (e.g. executor queueing). Repeat until the
                    # original target block ends, never after it is released.
                await self.registry._call(self.registry.client.expire, self.key, self.registry.ttl)
                try:
                    await asyncio.wait_for(self.stop.wait(), timeout=0.1)
                except TimeoutError:
                    pass

        watcher = asyncio.create_task(watch())
        try:
            try:
                yield
            except Exception:
                await self.seal()
                if self.requested:
                    raise QueryCancelled() from None
                raise
            else:
                await self.seal()
                if self.requested:
                    raise QueryCancelled()
        finally:
            self.stop.set()
            # Drain even an in-flight driver cancellation before rollback or
            # returning the connection: it must never hit the next borrower.
            try:
                await watcher
            finally:
                event.remove(sync_connection, "before_cursor_execute", capture_cursor)
                self.cursor = None


current_execution: ContextVar[TargetExecution | None] = ContextVar("target_execution", default=None)
