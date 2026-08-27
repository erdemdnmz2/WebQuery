"""Authentication-domain Redis-backed, process-shared login throttling."""

from __future__ import annotations

import asyncio
import hashlib
import os
import secrets
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from redis.asyncio import Redis
from redis.exceptions import RedisError


class LoginThrottleUnavailable(RuntimeError):
    """Raised when the required Redis throttle backend cannot be used."""


class LoginThrottle(Protocol):
    """Small interface that lets request tests supply a deterministic double."""

    async def retry_after_seconds(self, email: str, client_ip: str) -> int: ...

    async def record_failure(self, email: str, client_ip: str) -> None: ...

    async def clear_account(self, email: str) -> None: ...


@dataclass(frozen=True)
class LoginThrottleSettings:
    redis_url: str
    max_failures: int
    window_seconds: int
    key_prefix: str

    @classmethod
    def from_environment(cls) -> LoginThrottleSettings:
        redis_url = os.getenv("REDIS_URL", "").strip()
        max_failures = _positive_int("LOGIN_MAX_FAILURES", "5")
        window_minutes = _positive_int("LOGIN_WINDOW_MINUTES", "15")
        key_prefix = os.getenv("LOGIN_THROTTLE_KEY_PREFIX", "webquery:login-throttle").strip()

        if not redis_url:
            raise ValueError("REDIS_URL boş olamaz.")
        if not key_prefix:
            raise ValueError("LOGIN_THROTTLE_KEY_PREFIX boş olamaz.")

        return cls(
            redis_url=redis_url,
            max_failures=max_failures,
            window_seconds=window_minutes * 60,
            key_prefix=key_prefix,
        )


def _positive_int(name: str, default: str) -> int:
    raw_value = os.getenv(name, default)
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} pozitif tam sayı olmalıdır.") from exc
    if value <= 0:
        raise ValueError(f"{name} pozitif tam sayı olmalıdır.")
    return value


# Redis TIME is used rather than worker time, preventing clock drift from
# changing the shared sliding-window calculation. The key is one account or IP
# at a time, so the script remains atomic without a cross-key transaction.
_CHECK_SCRIPT = """
local time = redis.call('TIME')
local now = tonumber(time[1]) + tonumber(time[2]) / 1000000
local window = tonumber(ARGV[1])
local max_failures = tonumber(ARGV[2])
local cutoff = now - window

redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', cutoff)
local count = redis.call('ZCARD', KEYS[1])

if count >= max_failures then
    local oldest = redis.call('ZRANGE', KEYS[1], 0, 0, 'WITHSCORES')
    local retry_after = math.max(1, math.ceil(window - (now - tonumber(oldest[2]))))
    return {1, retry_after}
end

if count == 0 then
    redis.call('DEL', KEYS[1])
end
return {0, 0}
"""

_RECORD_FAILURE_SCRIPT = """
local time = redis.call('TIME')
local now = tonumber(time[1]) + tonumber(time[2]) / 1000000
local window = tonumber(ARGV[1])
local max_failures = tonumber(ARGV[2])
local cutoff = now - window

redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', cutoff)
local count = redis.call('ZCARD', KEYS[1])

if count >= max_failures then
    local oldest = redis.call('ZRANGE', KEYS[1], 0, 0, 'WITHSCORES')
    local retry_after = math.max(1, math.ceil(window - (now - tonumber(oldest[2]))))
    return {1, retry_after}
end

redis.call('ZADD', KEYS[1], now, ARGV[3])
redis.call('EXPIRE', KEYS[1], math.ceil(window) + 1)
return {0, 0}
"""


class RedisLoginThrottle:
    """Sliding-window login throttle shared by all application workers."""

    def __init__(self, settings: LoginThrottleSettings, client: Redis | None = None):
        self._settings = settings
        self._client = client or Redis.from_url(
            settings.redis_url,
            decode_responses=False,
            socket_connect_timeout=2,
            socket_timeout=2,
            health_check_interval=30,
        )

    @classmethod
    def from_environment(cls) -> RedisLoginThrottle:
        return cls(LoginThrottleSettings.from_environment())

    async def ping(self) -> None:
        try:
            await self._client.ping()
        except RedisError as exc:
            raise LoginThrottleUnavailable("Redis login throttle erişilemez.") from exc

    async def close(self) -> None:
        try:
            await self._client.aclose()
        except RedisError:
            # Shutdown cleanup must not mask a prior application shutdown error.
            pass

    async def retry_after_seconds(self, email: str, client_ip: str) -> int:
        responses = await self._run_for_keys(
            _CHECK_SCRIPT,
            (self._account_key(email), self._ip_key(client_ip)),
        )
        return max((wait for blocked, wait in responses if blocked), default=0)

    async def record_failure(self, email: str, client_ip: str) -> None:
        await self._run_for_keys(
            _RECORD_FAILURE_SCRIPT,
            (self._account_key(email), self._ip_key(client_ip)),
            secrets.token_urlsafe(18),
        )

    async def clear_account(self, email: str) -> None:
        try:
            await self._client.delete(self._account_key(email))
        except RedisError as exc:
            raise LoginThrottleUnavailable("Redis login throttle erişilemez.") from exc

    async def _run_for_keys(
        self,
        script: str,
        keys: Sequence[str],
        member: str | None = None,
    ) -> list[tuple[bool, int]]:
        args: tuple[int | str, ...] = (
            self._settings.window_seconds,
            self._settings.max_failures,
        )
        if member is not None:
            args += (member,)

        try:
            raw_responses = await asyncio.gather(
                *(self._client.eval(script, 1, key, *args) for key in keys)
            )
            return [self._parse_response(response) for response in raw_responses]
        except RedisError as exc:
            raise LoginThrottleUnavailable("Redis login throttle erişilemez.") from exc

    @staticmethod
    def _parse_response(response: object) -> tuple[bool, int]:
        if not isinstance(response, (list, tuple)) or len(response) != 2:
            raise LoginThrottleUnavailable("Redis login throttle geçersiz yanıt verdi.")
        try:
            blocked = bool(int(response[0]))
            retry_after = int(response[1])
        except (TypeError, ValueError) as exc:
            raise LoginThrottleUnavailable("Redis login throttle geçersiz yanıt verdi.") from exc
        return blocked, max(0, retry_after)

    def _account_key(self, email: str) -> str:
        return self._key("account", email.strip().lower())

    def _ip_key(self, client_ip: str) -> str:
        return self._key("ip", client_ip.strip())

    def _key(self, category: str, value: str) -> str:
        # Hashing prevents raw account and IP identifiers being exposed by Redis
        # key inspection or operational metrics.
        digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
        return f"{self._settings.key_prefix}:{category}:{digest}"
