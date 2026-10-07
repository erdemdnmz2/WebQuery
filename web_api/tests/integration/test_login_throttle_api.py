from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app import app
from app_database.models import AuditLog, User
from authentication.login_throttle import LoginThrottleUnavailable
from common.audit_actions import AuditAction


async def _register(async_client: AsyncClient, email: str = "throttle@example.com") -> None:
    response = await async_client.post(
        "/api/register",
        json={
            "username": "throttle_user",
            "email": email,
            "password": "StrongPassword123!",
        },
    )
    assert response.status_code == 200, response.text


@pytest.mark.asyncio
async def test_login_throttle_blocks_before_password_verification(async_client: AsyncClient):
    await _register(async_client)
    payload = {"email": "throttle@example.com", "password": "WrongPassword999!"}

    with patch.object(User, "check_password", return_value=False):
        for _ in range(5):
            response = await async_client.post("/api/login", json=payload)
            assert response.status_code == 400, response.text

    with patch.object(User, "check_password", side_effect=AssertionError("KDF çağrılmamalı")):
        response = await async_client.post("/api/login", json=payload)

    assert response.status_code == 429
    assert "Çok fazla başarısız giriş denemesi" in response.json()["detail"]


@pytest.mark.asyncio
async def test_redis_unavailable_rejects_login_before_password_verification(async_client: AsyncClient):
    await _register(async_client, email="unavailable@example.com")

    class UnavailableThrottle:
        async def retry_after_seconds(self, email: str, client_ip: str) -> int:
            raise LoginThrottleUnavailable("redis unavailable")

        async def record_failure(self, email: str, client_ip: str) -> None:
            raise AssertionError("record_failure çağrılmamalı")

        async def clear_account(self, email: str) -> None:
            raise AssertionError("clear_account çağrılmamalı")

    app.state.login_throttle = UnavailableThrottle()
    with patch.object(User, "check_password", side_effect=AssertionError("KDF çağrılmamalı")):
        response = await async_client.post(
            "/api/login",
            json={"email": "unavailable@example.com", "password": "StrongPassword123!"},
        )

    assert response.status_code == 503
    assert response.json()["detail"] == "Giriş koruması geçici olarak kullanılamıyor."


@pytest.mark.asyncio
async def test_redis_failure_while_recording_invalid_login_is_fail_closed(async_client: AsyncClient):
    await _register(async_client, email="record-unavailable@example.com")

    class RecordUnavailableThrottle:
        async def retry_after_seconds(self, email: str, client_ip: str) -> int:
            return 0

        async def record_failure(self, email: str, client_ip: str) -> None:
            raise LoginThrottleUnavailable("redis unavailable")

        async def clear_account(self, email: str) -> None:
            raise AssertionError("clear_account çağrılmamalı")

    app.state.login_throttle = RecordUnavailableThrottle()
    with patch.object(User, "check_password", return_value=False):
        response = await async_client.post(
            "/api/login",
            json={"email": "record-unavailable@example.com", "password": "WrongPassword999!"},
        )

    assert response.status_code == 503
    async with app.state.context.app_db.get_app_db() as db:
        audit = (
            await db.execute(select(AuditLog).where(AuditLog.action == AuditAction.LOGIN_FAILED))
        ).scalars().one()
    assert audit.client_ip == "127.0.0.1"


@pytest.mark.asyncio
async def test_redis_failure_while_clearing_successful_login_is_fail_closed(async_client: AsyncClient):
    await _register(async_client, email="clear-unavailable@example.com")

    class ClearUnavailableThrottle:
        async def retry_after_seconds(self, email: str, client_ip: str) -> int:
            return 0

        async def record_failure(self, email: str, client_ip: str) -> None:
            raise AssertionError("record_failure çağrılmamalı")

        async def clear_account(self, email: str) -> None:
            raise LoginThrottleUnavailable("redis unavailable")

    app.state.login_throttle = ClearUnavailableThrottle()
    with patch.object(User, "check_password", return_value=True):
        response = await async_client.post(
            "/api/login",
            json={"email": "clear-unavailable@example.com", "password": "StrongPassword123!"},
        )

    assert response.status_code == 503
    assert "access_token" not in response.json()


@pytest.mark.asyncio
async def test_successful_login_clears_account_counter_but_not_ip_counter(async_client: AsyncClient):
    await _register(async_client, email="clear@example.com")
    throttle = app.state.login_throttle
    wrong = {"email": "clear@example.com", "password": "WrongPassword999!"}
    correct = {"email": "clear@example.com", "password": "StrongPassword123!"}

    with patch.object(User, "check_password", side_effect=[False, True]):
        failed_response = await async_client.post("/api/login", json=wrong)
        successful_response = await async_client.post("/api/login", json=correct)

    assert failed_response.status_code == 400
    assert successful_response.status_code == 200, successful_response.text
    assert throttle.account_failures == {}
    assert throttle.ip_failures == {"127.0.0.1": 1}
