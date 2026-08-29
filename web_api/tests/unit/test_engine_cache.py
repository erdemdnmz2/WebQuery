import asyncio
import os
import sys
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add the web_api directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from database_provider.engine_cache import EngineCache, _now


# Helper to mock AsyncEngine
def get_mock_engine():
    mock_engine = MagicMock()
    mock_engine.dispose = AsyncMock()
    mock_engine.sync_engine.pool.checkedout = MagicMock(return_value=0) # Inactive by default
    return mock_engine

@pytest.fixture
def mock_create_engine():
    with patch("database_provider.engine_cache.create_async_engine") as mock:
        mock.side_effect = lambda *args, **kwargs: get_mock_engine()
        yield mock

@pytest.mark.asyncio
async def test_engine_reusability(mock_create_engine):
    """Test that the same URL returns the exact same engine from cache."""
    cache = EngineCache(max_engines=5)
    
    url = "mssql+aioodbc://fake:fake@host/db"
    
    engine1 = await cache.get_engine(url)
    engine2 = await cache.get_engine(url)
    
    # create_engine should have been called only once
    mock_create_engine.assert_called_once()
    
    # engine instances should be identical
    assert engine1 is engine2
    assert cache._stats["engine_count"] == 1
    assert cache._stats["request_count"] == 2


@pytest.mark.asyncio
async def test_engine_forwards_connect_args(mock_create_engine):
    cache = EngineCache(max_engines=5)
    connect_args = {"timeout": 120}

    await cache.get_engine(
        "mssql+aioodbc://fake:fake@host/db",
        connect_args=connect_args,
    )

    assert mock_create_engine.call_args.kwargs["connect_args"] == connect_args

@pytest.mark.asyncio
async def test_lru_eviction(mock_create_engine):
    """Test that LRU evicts the oldest inactive engine when max_engines is reached."""
    cache = EngineCache(max_engines=2)
    
    url1 = "mssql+aioodbc://fake:fake@host/db1"
    url2 = "mssql+aioodbc://fake:fake@host/db2"
    url3 = "mssql+aioodbc://fake:fake@host/db3"
    
    engine1 = await cache.get_engine(url1)
    # Wait a bit to ensure last_accessed timestamps are different
    await asyncio.sleep(0.01)
    engine2 = await cache.get_engine(url2)
    
    assert cache._stats["engine_count"] == 2
    
    # Access url1 again so it's the most recently used
    await cache.get_engine(url1)
    
    # Adding url3 should evict url2 because url1 was recently accessed
    await cache.get_engine(url3)
    
    assert cache._stats["engine_count"] == 2
    
    # Ensure url2's engine was disposed
    engine2.dispose.assert_awaited_once()
    
    # Ensure url1's engine was NOT disposed
    engine1.dispose.assert_not_awaited()

@pytest.mark.asyncio
async def test_ttl_cleanup(mock_create_engine):
    """Test that the background loop cleans up stale engines."""
    cache = EngineCache(max_engines=5)
    # Fast interval for test
    cache.time_interval = 0.1 
    
    url = "mssql+aioodbc://fake:fake@host/db"
    engine = await cache.get_engine(url)
    
    # Artificially age the entry to bypass wait time
    key = cache._hash_key(url)
    # Must use the cache's own clock: `datetime.now()` is local time, so on a
    # non-UTC server this "aged" value can land in the future and the entry
    # never expires.
    cache._cache[key].engines["ro"].last_accessed = _now() - timedelta(seconds=10)
    
    # Start loop and wait for it to process
    await cache.start_loop()
    await asyncio.sleep(0.15) 
    await cache.stop_loop()
    
    # Engine should have been disposed and removed from cache
    engine.dispose.assert_awaited_once()
    assert cache._stats["engine_count"] == 0

@pytest.mark.asyncio
async def test_database_tiers_receive_distinct_engines(mock_create_engine):
    cache = EngineCache(max_engines=5)

    ro = await cache.get_engine("postgresql+asyncpg://ro:p@host/db", db_uuid="db-1", tier="ro")
    rw = await cache.get_engine("postgresql+asyncpg://rw:p@host/db", db_uuid="db-1", tier="rw")

    assert ro is not rw
    assert set(cache._cache["db-1"].engines) == {"ro", "rw"}


@pytest.mark.asyncio
async def test_password_rotation_replaces_only_matching_tier_engine(mock_create_engine):
    cache = EngineCache(max_engines=5)
    old_ro = await cache.get_engine("postgresql+asyncpg://ro:old@host/db", db_uuid="db-1", tier="ro")
    rw = await cache.get_engine("postgresql+asyncpg://rw:stable@host/db", db_uuid="db-1", tier="rw")

    new_ro = await cache.get_engine("postgresql+asyncpg://ro:new@host/db", db_uuid="db-1", tier="ro")

    assert old_ro is not new_ro
    old_ro.dispose.assert_awaited_once()
    assert cache._cache["db-1"].engines["rw"].engine is rw


@pytest.mark.asyncio
async def test_close_database_engines_disposes_all_tiers(mock_create_engine):
    cache = EngineCache(max_engines=5)
    ro = await cache.get_engine("postgresql+asyncpg://ro:p@host/db", db_uuid="db-1", tier="ro")
    rw = await cache.get_engine("postgresql+asyncpg://rw:p@host/db", db_uuid="db-1", tier="rw")

    assert await cache.close_database_engines("db-1") == 2
    ro.dispose.assert_awaited_once()
    rw.dispose.assert_awaited_once()
    assert cache.get_cache_stats()["engine_count"] == 0
