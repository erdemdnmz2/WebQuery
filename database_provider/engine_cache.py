import hashlib
from typing import Dict
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, AsyncSession, async_sessionmaker


class EngineCache:
    def __init__(self, max_engines = 100):
        self._cache : Dict[str, AsyncEngine] = {}
        self._max_engines = max_engines
        
    