import asyncio
import hashlib
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from .config import TIME_INTERVAL_FOR_CACHE, apply_statement_timeout

logger = logging.getLogger(__name__)

class EngineCacheExhaustedError(RuntimeError):
    """Raised when the cache is at capacity and no pool can be evicted safely."""


_POOL_BY_TIER = {
    "ro": {"pool_size": 10, "max_overflow": 20},
    "rw": {"pool_size": 5, "max_overflow": 10},
    "ddl": {"pool_size": 1, "max_overflow": 2},
}


def _now() -> datetime:
    """Return a timezone-safe value compatible with existing naive cache metadata."""
    return datetime.now(UTC).replace(tzinfo=None)


@dataclass
class TierEngineEntry:
    """One target database connection pool for one least-privilege tier."""

    engine: AsyncEngine
    credential_fingerprint: str
    last_accessed: datetime = field(default_factory=_now)


@dataclass
class EngineCacheEntry:
    """All lazily-created connection pools for one target database UUID."""

    db_uuid: str
    engines: dict[str, TierEngineEntry] = field(default_factory=dict)


class EngineCache:
    def __init__(self, max_engines: int = 100):
        self._cache: dict[str, EngineCacheEntry] = {}
        self._max_engines = max_engines
        self.lock = asyncio.Lock()
        self._stats = {"engine_count": 0, "request_count": 0, "total_memory": 0}
        self.time_interval = TIME_INTERVAL_FOR_CACHE
        self._cleanup_task: asyncio.Task[None] | None = None
        self._running = False

    def _hash_key(self, url: str) -> str:
        """Hash a URL so passwords are never retained as cache metadata."""
        return hashlib.sha256(url.encode("utf-8")).hexdigest()

    def _is_engine_active(self, engine: AsyncEngine) -> bool:
        try:
            return engine.sync_engine.pool.checkedout() > 0
        except (AttributeError, TypeError):
            return False

    def _all_entries(self):
        for db_key, database_entry in self._cache.items():
            for tier, tier_entry in database_entry.engines.items():
                yield db_key, tier, tier_entry

    async def _evict_lru(self) -> None:
        """Evict the least-recently-used *idle* pool.

        Only idle pools are eligible. Disposing a pool with checked-out
        connections tears the pool out from under a query that is still running,
        so when every pool is busy the cache refuses to grow instead — the
        caller gets a clear error rather than a severed connection.
        """
        entries = list(self._all_entries())
        idle = [entry for entry in entries if not self._is_engine_active(entry[2].engine)]
        if not idle:
            raise EngineCacheExhaustedError(
                f"Engine cache is full ({self._max_engines}) and every pool is "
                "serving an active query; try again shortly."
            )
        db_key, tier, entry = min(idle, key=lambda item: item[2].last_accessed)
        del self._cache[db_key].engines[tier]
        if not self._cache[db_key].engines:
            del self._cache[db_key]
        await entry.engine.dispose()
        self._stats["engine_count"] -= 1

    async def get_engine(
        self,
        url: str,
        db_uuid: str | None = None,
        tier: str = "ro",
        connect_args: dict | None = None,
        tech: str | None = None,
        query_timeout_seconds: int = 0,
    ) -> AsyncEngine:
        """Return a pool keyed by target UUID and permission tier.

        ``db_uuid`` is always used by runtime target connections. Hash-keyed
        entries keep legacy unit callers isolated without exposing URLs.
        """
        if tier not in _POOL_BY_TIER:
            raise ValueError(f"Unsupported credential tier: {tier}")
        db_key = db_uuid or self._hash_key(url)
        fingerprint = self._hash_key(url)
        async with self.lock:
            database_entry = self._cache.setdefault(db_key, EngineCacheEntry(db_uuid=db_key))
            cached = database_entry.engines.get(tier)
            if cached is not None:
                if cached.credential_fingerprint == fingerprint:
                    cached.last_accessed = _now()
                    self._stats["request_count"] += 1
                    return cached.engine
                await cached.engine.dispose()
                del database_entry.engines[tier]
                self._stats["engine_count"] -= 1

            if self._stats["engine_count"] >= self._max_engines:
                await self._evict_lru()

            engine = create_async_engine(
                url,
                pool_timeout=30,
                pool_recycle=1800,
                # A target server restart or a firewall dropping an idle
                # connection leaves a stale entry in the pool; pool_recycle
                # narrows that window but does not close it. The cost is one
                # round-trip per checkout.
                pool_pre_ping=True,
                connect_args=connect_args or {},
                **_POOL_BY_TIER[tier],
            )
            if tech:
                apply_statement_timeout(engine, tech, query_timeout_seconds)
            database_entry = self._cache.setdefault(db_key, EngineCacheEntry(db_uuid=db_key))
            database_entry.engines[tier] = TierEngineEntry(
                engine=engine,
                credential_fingerprint=fingerprint,
            )
            self._stats["engine_count"] += 1
            self._stats["request_count"] += 1
            return engine

    def get_cache_stats(self) -> dict:
        return self._stats.copy()

    async def start_loop(self) -> None:
        if not self._running:
            self._cleanup_task = asyncio.create_task(self._loop())
            self._running = True

    async def _loop(self) -> None:
        while self._running:
            try:
                await asyncio.sleep(self.time_interval)
                async with self.lock:
                    cutoff = _now()
                    stale = [
                        (db_key, tier, entry)
                        for db_key, tier, entry in self._all_entries()
                        if (cutoff - entry.last_accessed).total_seconds() > self.time_interval
                        and not self._is_engine_active(entry.engine)
                    ]
                    for db_key, tier, entry in stale:
                        database_entry = self._cache.get(db_key)
                        if database_entry and database_entry.engines.get(tier) is entry:
                            del database_entry.engines[tier]
                            if not database_entry.engines:
                                del self._cache[db_key]
                            await entry.engine.dispose()
                            self._stats["engine_count"] -= 1
            except asyncio.CancelledError:
                break
            except Exception:
                # An unexpected failure here used to end the loop silently,
                # which meant TTL cleanup never ran again for the lifetime of
                # the process and nothing said so. Log and keep the loop alive.
                logger.exception(
                    "Engine cache temizlik döngüsünde beklenmeyen hata; döngü sürüyor"
                )

    async def stop_loop(self) -> None:
        if self._running:
            self._running = False
            if self._cleanup_task:
                self._cleanup_task.cancel()
                try:
                    await self._cleanup_task
                except asyncio.CancelledError:
                    pass
        async with self.lock:
            for _db_key, _tier, entry in list(self._all_entries()):
                await entry.engine.dispose()
            self._cache.clear()
            self._stats["engine_count"] = 0

    async def close_database_engines(self, db_uuid: str) -> int:
        """Dispose every tier pool for a target database immediately."""
        async with self.lock:
            database_entry = self._cache.pop(db_uuid, None)
            if database_entry is None:
                return 0
            for entry in database_entry.engines.values():
                await entry.engine.dispose()
            count = len(database_entry.engines)
            self._stats["engine_count"] -= count
            return count
