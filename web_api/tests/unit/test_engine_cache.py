import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timedelta
import sys
import os

# Add the web_api directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from database_provider.engine_cache import EngineCache

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
    cache._cache[key].last_accessed = datetime.now() - timedelta(seconds=10)
    
    # Start loop and wait for it to process
    await cache.start_loop()
    await asyncio.sleep(0.15) 
    await cache.stop_loop()
    
    # Engine should have been disposed and removed from cache
    engine.dispose.assert_awaited_once()
    assert cache._stats["engine_count"] == 0

@pytest.mark.asyncio
async def test_close_user_engines(mock_create_engine):
    """Test that close_user_engines clears engines for a specific user ID."""
    cache = EngineCache(max_engines=5)
    
    url1 = "mssql+aioodbc://fake:fake@host/db1"
    url2 = "mssql+aioodbc://fake:fake@host/db2"
    
    # User 1 has engine 1
    engine1 = await cache.get_engine(url1, owner_id=1)
    
    # User 2 has engine 2
    engine2 = await cache.get_engine(url2, owner_id=2)
    
    assert cache._stats["engine_count"] == 2
    
    await cache.close_user_engines(user_id=1)
    
    # Engine 1 should be disposed, engine 2 should remain
    engine1.dispose.assert_awaited_once()
    engine2.dispose.assert_not_awaited()
    
    assert cache._stats["engine_count"] == 1
