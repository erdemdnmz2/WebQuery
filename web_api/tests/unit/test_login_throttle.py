from unittest.mock import AsyncMock, MagicMock

import pytest
from redis.exceptions import RedisError

from authentication.login_throttle import (
    LoginThrottleSettings,
    LoginThrottleUnavailable,
    RedisLoginThrottle,
)


def _settings() -> LoginThrottleSettings:
    return LoginThrottleSettings(
        redis_url="redis://localhost:6379/15",
        max_failures=5,
        window_seconds=900,
        key_prefix="webquery:test:login-throttle",
    )


@pytest.mark.asyncio
async def test_retry_uses_hashed_account_and_ip_keys_and_returns_longest_wait():
    client = MagicMock()
    client.eval = AsyncMock(side_effect=[[0, 0], [1, 37]])
    throttle = RedisLoginThrottle(_settings(), client=client)

    wait = await throttle.retry_after_seconds("Person@example.com", "203.0.113.10")

    assert wait == 37
    assert client.eval.await_count == 2
    keys = [call.args[2] for call in client.eval.await_args_list]
    assert all("Person@example.com" not in key for key in keys)
    assert all("203.0.113.10" not in key for key in keys)
    assert any(":account:" in key for key in keys)
    assert any(":ip:" in key for key in keys)


@pytest.mark.asyncio
async def test_record_failure_runs_atomic_script_for_both_dimensions():
    client = MagicMock()
    client.eval = AsyncMock(return_value=[0, 0])
    throttle = RedisLoginThrottle(_settings(), client=client)

    await throttle.record_failure("person@example.com", "203.0.113.10")

    assert client.eval.await_count == 2
    first_call = client.eval.await_args_list[0]
    assert "ZADD" in first_call.args[0]
    assert first_call.args[1] == 1
    assert len(first_call.args) == 6  # script, numkeys, key, window, limit, unique member


@pytest.mark.asyncio
async def test_redis_error_is_reported_as_throttle_unavailable():
    client = MagicMock()
    client.eval = AsyncMock(side_effect=RedisError("connection lost"))
    throttle = RedisLoginThrottle(_settings(), client=client)

    with pytest.raises(LoginThrottleUnavailable):
        await throttle.retry_after_seconds("person@example.com", "203.0.113.10")


@pytest.mark.asyncio
async def test_successful_login_only_clears_the_account_key():
    client = MagicMock()
    client.delete = AsyncMock(return_value=1)
    throttle = RedisLoginThrottle(_settings(), client=client)

    await throttle.clear_account("person@example.com")

    client.delete.assert_awaited_once()
    deleted_key = client.delete.await_args.args[0]
    assert ":account:" in deleted_key
    assert ":ip:" not in deleted_key


@pytest.mark.asyncio
async def test_startup_ping_failure_is_fail_closed():
    client = MagicMock()
    client.ping = AsyncMock(side_effect=RedisError("connection refused"))
    throttle = RedisLoginThrottle(_settings(), client=client)

    with pytest.raises(LoginThrottleUnavailable):
        await throttle.ping()
