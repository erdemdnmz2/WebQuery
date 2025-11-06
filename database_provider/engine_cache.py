import hashlib
from typing import Dict
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, AsyncSession, async_sessionmaker
import asyncio


class EngineCache:
    def __init__(self, max_engines = 100):
        self._cache : Dict[str, AsyncEngine] = {}
        self._max_engines = max_engines
        self.lock = asyncio.Lock()
        self._stats = {
            "engine_count": 0,
            "request_count": 0,
            "total_memory" : 0,
        }

    def _hash_key(self, url: str) -> str:
        byte_data = url.encode("utf-8")

        hash = hashlib.sha256(byte_data).hexdigest()[:16]

        return hash

    async def get_engine(self, url: str):
        hash_key = self._hash_key(url=url)

        async with self.lock:
            
            if hash_key in self._cache:
                self._stats["request_count"] += 1
                return self._cache[hash_key]
            
            if self._stats["engine_count"] >= self._max_engines:
                return None
            
            engine = create_async_engine(
                url,
                pool_size=1,
                max_overflow=1,
                pool_timeout=30,
                pool_recycle=1800,
                pool_pre_ping=True
            )
            
            self._cache[hash_key] = engine
            self._stats["engine_count"] += 1
            self._stats["request_count"] += 1
            
            return engine
        
    def get_cache_stats(self):
        return self._stats