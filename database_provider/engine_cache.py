import hashlib
from typing import Dict
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, AsyncSession, async_sessionmaker
import asyncio
from config import TIME_INTERVAL_FOR_CACHE
from pydantic import BaseModel, Field
from datetime import datetime


class EngineCacheEntry(BaseModel):
    """Cached engine entry with metadata"""
    engine: AsyncEngine
    last_accessed: datetime = Field(default_factory=datetime.now)
    
    class Config:
        arbitrary_types_allowed = True  

class EngineCache:
    def __init__(self, max_engines = 100):
        self._cache : Dict[str, EngineCacheEntry] = {}
        self._max_engines = max_engines
        self.lock = asyncio.Lock()
        self._stats = {
            "engine_count": 0,
            "request_count": 0,
            "total_memory" : 0,
        }

        self.time_interval = TIME_INTERVAL_FOR_CACHE

        self._cleanup_task = None
        self._running = False

    def _hash_key(self, url: str) -> str:
        byte_data = url.encode("utf-8")

        hash = hashlib.sha256(byte_data).hexdigest()[:16]

        return hash

    async def get_engine(self, url: str) -> AsyncEngine:
        hash_key = self._hash_key(url=url)

        async with self.lock:
            
            if hash_key in self._cache:
                self._cache[hash_key].last_accessed = datetime.now()
                self._stats["request_count"] += 1
                return self._cache[hash_key].engine
            
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

            entry = EngineCacheEntry(engine=engine, last_accessed=datetime.now())
            
            self._cache[hash_key] = entry
            self._stats["engine_count"] += 1
            self._stats["request_count"] += 1
            
            return engine
        
    def get_cache_stats(self) -> Dict:
        return self._stats
    
    async def start_loop(self):
        if not self._running:
            self._cleanup_task = asyncio.create_task(self._loop())
            self._running = True

    #TODO açık transaction var mı onu kontrol et
    async def _loop(self):
        while self._running:
            try:
                await asyncio.sleep(self.time_interval)
                
                # Lock ile güvenli temizlik
                async with self.lock:
                    current_time = datetime.now()
                    stale_keys = []
                    
                    for key, entry in self._cache.items():
                        time_since_access = (current_time - entry.last_accessed).total_seconds()
                        if time_since_access > self.time_interval:
                            stale_keys.append(key)
                    
                    for key in stale_keys:
                        entry = self._cache.pop(key)
                        await entry.engine.dispose()
                        self._stats["engine_count"] -= 1
                        
            except asyncio.CancelledError:
                break

    async def stop_loop(self):
        if self._running:
            try:
                self._running = False
                if self._cleanup_task:
                    self._cleanup_task.cancel()
                    try:
                        await self._cleanup_task 
                    except asyncio.CancelledError:
                        pass
                self._cleanup_task = None
            except Exception as e:
                print(f"Error: {e}")
            
            disposed_engine_count = 0
            async with self.lock:
                for entry in list(self._cache.values()):
                    try:
                        await entry.engine.dispose()
                        disposed_engine_count += 1
                    except Exception as e:
                        print(f"Error occured during cleaning cache: {e}")

            self._cache.clear()
            self._stats["engine_count"] = 0
            print(f"[EngineCache] Disposed {disposed_engine_count} engines")
