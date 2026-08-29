import os
import sys
from unittest.mock import AsyncMock, MagicMock

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
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")

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


def make_target_session_mock():
    """A target-session double that serves both execution paths.

    Reads go through `AsyncSession.stream()` so a large result set is never
    materialised in the worker (P1-5); writes and anything the planner cannot
    classify as a plain read still go through `execute()`. Both are wired to the
    same `mock_result`, so a test only has to set `returns_rows` and
    `fetchmany.return_value` as before.

    Returns:
        tuple: (mock_session, mock_result)
    """
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_session.execute.return_value = mock_result

    stream_result = AsyncMock()
    stream_result.fetchmany = AsyncMock(
        side_effect=lambda size=None: mock_result.fetchmany(size=size)
    )
    stream_result.close = AsyncMock()
    mock_session.stream = AsyncMock(return_value=stream_result)

    return mock_session, mock_result


class FakeLoginThrottle:
    """Test double; production always uses RedisLoginThrottle."""

    def __init__(self, max_failures: int = 5):
        self.max_failures = max_failures
        self.account_failures: dict[str, int] = {}
        self.ip_failures: dict[str, int] = {}

    async def retry_after_seconds(self, email: str, client_ip: str) -> int:
        account_count = self.account_failures.get(email.strip().lower(), 0)
        ip_count = self.ip_failures.get(client_ip, 0)
        return 60 if max(account_count, ip_count) >= self.max_failures else 0

    async def record_failure(self, email: str, client_ip: str) -> None:
        account = email.strip().lower()
        self.account_failures[account] = self.account_failures.get(account, 0) + 1
        self.ip_failures[client_ip] = self.ip_failures.get(client_ip, 0) + 1

    async def clear_account(self, email: str) -> None:
        self.account_failures.pop(email.strip().lower(), None)


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
    app.state.login_throttle = FakeLoginThrottle()

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
