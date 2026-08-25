import os
import sys

import pytest
from httpx import ASGITransport, AsyncClient

# Mock APP_DATABASE_URL before any app modules are imported
os.environ["APP_DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ.setdefault("SECRET_KEY", "test-only-secret-key-with-at-least-32-chars")
os.environ.setdefault(
    "QUERY_ENCRYPTION_KEY",
    "CS8EY9zwmjvdAelb-8wdVdyyVDP-y7rkXeZ-ATMRZk4=",
)
os.environ.setdefault("CENTRAL_DB_USER", "test-central-user")
os.environ.setdefault("CENTRAL_DB_PASSWORD", "test-central-password")
os.environ.setdefault("ALLOWED_EMAIL_DOMAINS", "example.com")
os.environ.setdefault("REGISTRATION_REQUIRES_ACTIVATION", "false")

# slack_integration/config.py reads these at import time with no default;
# `from app import app` below pulls that module in transitively. Without a
# value here, SlackListener() raises BoltError("... token ... required")
# in any environment that doesn't happen to have real Slack credentials in
# its .env (e.g. CI). Tests that exercise Slack behavior mock the actual
# network calls (see test_notifications_and_slack.py) — these are just
# enough to let SlackListener/AsyncApp construct.
os.environ.setdefault("SLACK_BOT_TOKEN", "xoxb-test-token")
os.environ.setdefault("SLACK_APP_TOKEN", "xapp-test-token")
os.environ.setdefault("SLACK_ADMIN_CHANNEL", "C_TEST_CHANNEL")

# Add the web_api directory to sys.path so we can import the app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app

# Mark all async tests to use asyncio automatically
pytestmark = pytest.mark.asyncio

import pytest_asyncio

from app_database import AppDatabase
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
    await app.state.db_provider.start_cache_loop()

    from dependencies import AppContext
    app.state.context = AppContext(
        app_db=app.state.app_db,
        db_provider=app.state.db_provider
    )
    
    # Disable rate limiter for testing to prevent 429 Too Many Requests
    if hasattr(app.state, "limiter"):
        app.state.limiter.enabled = False
    
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client
    finally:
        # Without this, the EngineCache background cleanup loop
        # (asyncio.create_task in engine_cache.py) outlives the test and
        # keeps the interpreter alive — pytest hangs after printing its
        # final summary instead of exiting.
        await app.state.db_provider.close_engines()
        await app.state.app_db.app_engine.dispose()
