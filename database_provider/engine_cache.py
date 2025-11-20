import hashlib
from typing import Dict, Optional
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import QueuePool
import asyncio
from config import TIME_INTERVAL_FOR_CACHE
from pydantic import BaseModel, Field
from datetime import datetime


class EngineCacheEntry(BaseModel):
    """Cached engine entry with metadata"""
    engine: AsyncEngine
    last_accessed: datetime = Field(default_factory=datetime.now)
    owner_id: Optional[int] = None
    
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

    def _is_engine_active(self, engine: AsyncEngine) -> bool:
        """Engine üzerinde aktif transaction/connection var mı kontrol eder"""
        try:
            # checkedout > 0 ise havuzdan alınmış ve henüz geri dönmemiş bağlantı var demektir
            return engine.sync_engine.pool.checkedout() > 0
        except Exception:
            return False

    async def _evict_lru(self):
        """LRU Eviction: Yer açmak için en eski ve boşta olan engine'i siler"""
        # 1. Aktif olmayan (idle) motorları bul
        idle_engines = {
            k: v for k, v in self._cache.items() 
            if not self._is_engine_active(v.engine)
        }
        
        if idle_engines:
            oldest_key = min(idle_engines.keys(), key=lambda k: idle_engines[k].last_accessed)
            print(f"[EngineCache] LRU: Evicting idle engine: {oldest_key}")
        else:
            oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k].last_accessed)
            print(f"[EngineCache] WARNING: Cache full & all active. Force evicting: {oldest_key}")
        
        entry = self._cache.pop(oldest_key)
        await entry.engine.dispose()
        self._stats["engine_count"] -= 1

    async def get_engine(self, url: str, owner_id: int = None) -> AsyncEngine:
        hash_key = self._hash_key(url=url)

        async with self.lock:
            
            if hash_key in self._cache:
                self._cache[hash_key].last_accessed = datetime.now()
                self._stats["request_count"] += 1
                return self._cache[hash_key].engine
            
            if self._stats["engine_count"] >= self._max_engines:
                await self._evict_lru()
                        
            engine = create_async_engine(
                url,
                poolclass=QueuePool,
                pool_size=0,
                max_overflow=20,
                pool_timeout=30,
                pool_recycle=1800,
                pool_pre_ping=True
            )

            entry = EngineCacheEntry(
                engine=engine, 
                last_accessed=datetime.now(),
                owner_id=owner_id
            )
            
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
            print("[EngineCache] Background cleanup loop started.")

    async def _loop(self):
        """Zaman aşımına uğrayanları temizleyen döngü (TTL)"""
        while self._running:
            try:
                await asyncio.sleep(self.time_interval)
                
                async with self.lock:
                    if self._stats["engine_count"] < self._max_engines:
                        current_time = datetime.now()
                        stale_keys = []
                        
                        for key, entry in self._cache.items():
                            time_since_access = (current_time - entry.last_accessed).total_seconds()
                            
                            # Süresi dolmuş VE aktif işlemi olmayanları seç
                            if time_since_access > self.time_interval and not self._is_engine_active(entry.engine):
                                stale_keys.append(key)
                        
                        for key in stale_keys:
                            entry = self._cache.pop(key)
                            await entry.engine.dispose()
                            self._stats["engine_count"] -= 1
                        
                        if stale_keys:
                            print(f"[EngineCache] TTL Cleanup: Removed {len(stale_keys)} idle engines.")

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[EngineCache] Error in loop: {e}")

    async def stop_loop(self):
        if self._running:
            self._running = False
            if self._cleanup_task:
                self._cleanup_task.cancel()
                try:
                    await self._cleanup_task 
                except asyncio.CancelledError:
                    pass
            
            async with self.lock:
                for entry in list(self._cache.values()):
                    await entry.engine.dispose()
                self._cache.clear()
                self._stats["engine_count"] = 0
            print(f"[EngineCache] Stopped and cleared all engines.")
    
    async def close_user_engines(self, user_id: int):
        """Belirli bir kullanıcı ID'sine ait motorları kapatır"""
        if not user_id:
            return

        keys_to_remove = []
        async with self.lock:
            for key, entry in self._cache.items():
                if entry.owner_id == user_id:
                    if not self._is_engine_active(entry.engine):
                        keys_to_remove.append(key)
            
            for key in keys_to_remove:
                entry = self._cache.pop(key)
                await entry.engine.dispose()
                self._stats["engine_count"] -= 1
                print(f"[EngineCache] Closed engine for user_id: {user_id}")
