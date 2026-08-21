"""Server-side sessions and rotating refresh tokens."""

import hashlib
import os
import secrets
from datetime import UTC, datetime, timedelta

from jose import jwt
from sqlalchemy import select, update

from app_database.models import User, UserSession
from authentication import config

ACCESS_TTL_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "20"))
REFRESH_TTL_HOURS = int(os.getenv("REFRESH_TOKEN_EXPIRE_HOURS", "12"))
REFRESH_GRACE_SECONDS = int(os.getenv("REFRESH_GRACE_SECONDS", "30"))


def _db_now() -> datetime:
    """Return naive UTC for the existing cross-database AppDateTime columns."""
    return datetime.now(UTC).replace(tzinfo=None)


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def mint_access(user_id: int, session_id: int) -> str:
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": str(user_id),
            "sid": session_id,
            "iat": now,
            "exp": now + timedelta(minutes=ACCESS_TTL_MINUTES),
        },
        config.SECRET_KEY,
        algorithm=config.ALGORITHM,
    )


async def create_session(app_db, user_id: int, client_ip: str | None,
                         user_agent: str | None) -> tuple[int, str]:
    token = secrets.token_urlsafe(48)
    now = _db_now()
    async with app_db.get_app_db() as db:
        async with db.begin():
            session = UserSession(
                user_id=user_id,
                refresh_hash=_hash(token),
                created_at=now,
                expires_at=now + timedelta(hours=REFRESH_TTL_HOURS),
                client_ip=client_ip,
                user_agent=(user_agent or "")[:300],
            )
            db.add(session)
            await db.flush()
            return session.id, token


async def session_alive(app_db, session_id: int, user_id: int) -> bool:
    async with app_db.get_app_db() as db:
        row = (await db.execute(
            select(UserSession.id).where(
                UserSession.id == session_id,
                UserSession.user_id == user_id,
                UserSession.revoked_at.is_(None),
                UserSession.expires_at > _db_now(),
            )
        )).first()
        return row is not None


async def rotate_refresh(app_db, refresh_token: str) -> dict | None:
    old_hash = _hash(refresh_token)
    new_token = secrets.token_urlsafe(48)
    now = _db_now()

    async with app_db.get_app_db() as db:
        async with db.begin():
            result = await db.execute(
                select(UserSession).where(
                    UserSession.refresh_hash == old_hash,
                    UserSession.revoked_at.is_(None),
                    UserSession.expires_at > now,
                ).with_for_update()
            )
            session = result.scalars().first()
            if session:
                session.prev_refresh_hash = old_hash
                session.refresh_hash = _hash(new_token)
                session.last_refresh_at = now
                return {
                    "session_id": session.id,
                    "user_id": session.user_id,
                    "refresh_token": new_token,
                }

            # A recently rotated token can be presented by a second browser tab.
            result = await db.execute(
                select(UserSession).where(
                    UserSession.prev_refresh_hash == old_hash,
                    UserSession.revoked_at.is_(None),
                    UserSession.expires_at > now,
                    UserSession.last_refresh_at > now - timedelta(seconds=REFRESH_GRACE_SECONDS),
                ).with_for_update()
            )
            session = result.scalars().first()
            if session:
                session.prev_refresh_hash = old_hash
                session.refresh_hash = _hash(new_token)
                session.last_refresh_at = now
                return {
                    "session_id": session.id,
                    "user_id": session.user_id,
                    "refresh_token": new_token,
                }

            result = await db.execute(
                update(UserSession)
                .where(UserSession.prev_refresh_hash == old_hash,
                       UserSession.revoked_at.is_(None))
                .values(revoked_at=now,
                        revoked_reason="refresh token tekrar kullanımı tespit edildi")
            )
            if result.rowcount:
                return {"reuse": True}
    return None


async def revoke_session(app_db, session_id: int, reason: str) -> None:
    async with app_db.get_app_db() as db:
        async with db.begin():
            await db.execute(
                update(UserSession)
                .where(UserSession.id == session_id,
                       UserSession.revoked_at.is_(None))
                .values(revoked_at=_db_now(), revoked_reason=reason)
            )


async def revoke_user_sessions(app_db, user_id: int, reason: str) -> int:
    async with app_db.get_app_db() as db:
        async with db.begin():
            result = await db.execute(
                update(UserSession)
                .where(UserSession.user_id == user_id,
                       UserSession.revoked_at.is_(None))
                .values(revoked_at=_db_now(), revoked_reason=reason)
            )
            return result.rowcount or 0
