import pytest
from httpx import AsyncClient, ASGITransport
import sys
import os
# Mock APP_DATABASE_URL before any app modules are imported
os.environ["APP_DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

# Add the web_api directory to sys.path so we can import the app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app

# Mark all async tests to use asyncio automatically
pytestmark = pytest.mark.asyncio

import pytest_asyncio
from app_database import AppDatabase
from cryptography.fernet import Fernet
from session import SessionCache
from database_provider import DatabaseProvider

@pytest_asyncio.fixture
async def async_client():
    """
    Fixture for providing an asynchronous HTTP client that bypasses the actual network
    and directly calls the ASGI application.
    """
    # Manually setup state for testing
    app.state.app_db = AppDatabase()
    await app.state.app_db.create_tables()
    
    app.state.db_provider = DatabaseProvider()
    app.state.fernet = Fernet(Fernet.generate_key())
    import fakeredis
    fake_redis = fakeredis.FakeRedis()
    
    # We monkeypatch the session cache's redis client
    app.state.session_cache = SessionCache(fernet=app.state.fernet)
    app.state.session_cache.client = fake_redis
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
