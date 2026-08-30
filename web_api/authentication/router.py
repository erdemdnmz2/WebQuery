"""
Authentication Router Module
FastAPI router for user login, registration, logout, and self-information.
Strictly typed and documented.
"""
import logging
import os
from typing import Any

import anyio.to_thread
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from jose import JWTError, jwt
from sqlalchemy import update
from sqlalchemy.future import select

from app_database.app_database import AppDatabase
from app_database.models import (
    User,
    UserDatabaseAssociation,
    UserSession,
    burn_password_check,
    hash_password,
    validate_password_policy,
)
from authentication import config, schemas, sessions
from authentication.login_throttle import LoginThrottle, LoginThrottleUnavailable
from authentication.services import get_current_user
from common.audit import log_in, log_standalone
from common.audit_actions import AuditAction, AuditTarget
from common.audit_details import (
    PasswordChangeAuditDetails,
    SessionAuditDetails,
    UserLifecycleAuditDetails,
)
from common.clock import db_now
from common.limiter import limiter
from common.roles import any_admin
from dependencies import get_app_db

router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)

# Using centralized limiter
ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"
ACCESS_COOKIE_PATH = "/"
REFRESH_COOKIE_PATH = "/api/refresh"
LEGACY_REFRESH_COOKIE_PATH = "/api"


def _clear_legacy_refresh_cookie(response: Response) -> None:
    """Remove the broader refresh cookie issued before the path hardening."""
    response.delete_cookie(
        key=REFRESH_COOKIE,
        secure=os.getenv("COOKIE_SECURE", "False").lower() == "true",
        samesite="strict",
        httponly=True,
        path=LEGACY_REFRESH_COOKIE_PATH,
    )


def get_login_throttle(request: Request) -> LoginThrottle:
    """Return the startup-initialised, mandatory login throttle backend."""
    throttle = getattr(request.app.state, "login_throttle", None)
    if throttle is None:
        raise HTTPException(
            status_code=503,
            detail="Giriş koruması geçici olarak kullanılamıyor.",
        )
    return throttle


# One acknowledgement for every registration attempt, taken or not. Activation
# is an OWNER decision in all cases, so this wording is accurate either way and
# does not confirm whether an address is already registered.
_REGISTRATION_ACK = (
    "Kayıt başvurunuz alındı. Yönetici hesabınızı etkinleştirdiğinde "
    "giriş yapabilirsiniz."
)


def _current_session_id(request: Request) -> int | None:
    """The session id carried by the caller's own access token, if readable."""
    token = request.cookies.get(ACCESS_COOKIE)
    if not token:
        return None
    try:
        payload = jwt.decode(token, config.SECRET_KEY, algorithms=[config.ALGORITHM])
        session_id = payload.get("sid")
        return int(session_id) if session_id is not None else None
    except (JWTError, TypeError, ValueError):
        return None


def _throttle_unavailable() -> HTTPException:
    return HTTPException(
        status_code=503,
        detail="Giriş koruması geçici olarak kullanılamıyor.",
    )


@router.post("/login", response_model=schemas.LoginResponse)
@limiter.limit(config.RATE_LIMITER)
async def login(
    user: schemas.UserLogin,
    response: Response,
    request: Request,
    app_db: AppDatabase = Depends(get_app_db),
    throttle: LoginThrottle = Depends(get_login_throttle),
) -> dict[str, bool]:
    """
    User login endpoint.
    Verifies credentials, creates JWT token, and writes login logs.
    
    Args:
        user: The user login credentials payload.
        response: The FastAPI response object (used to set auth cookies).
        request: The FastAPI request object (used for client IP logging).
        app_db: The application database manager instance.
        
    Returns:
        dict[str, bool]: Cookie-based session creation acknowledgement.
    """
    client_ip: str = request.client.host if request.client else "unknown"
    try:
        wait = await throttle.retry_after_seconds(user.email, client_ip)
    except LoginThrottleUnavailable:
        raise _throttle_unavailable() from None

    if wait:
        raise HTTPException(
            status_code=429,
            detail=(
                "Çok fazla başarısız giriş denemesi. "
                f"Yaklaşık {max(1, wait // 60)} dakika sonra tekrar deneyin."
            ),
        )

    # The password check costs 1-2 seconds of CPU at rounds=14. It runs on a
    # worker thread (so the event loop keeps serving) and outside the database
    # session (so a connection is not held open for that whole time). It used to
    # do neither: one login stalled the entire worker and pinned an app-DB
    # connection while it did.
    async with app_db.get_app_db() as db:
        result = await db.execute(select(User).where(User.email == user.email))
        candidate: User | None = result.scalars().first()
        password_hash = candidate.password if candidate else None
        is_active = bool(candidate.is_active) if candidate else False

    if candidate is None or not password_hash:
        # No account: spend the same CPU anyway so a miss and a wrong password
        # take the same time. Otherwise the response latency answers "does this
        # address exist here?" no matter what the body says.
        await burn_password_check()
        password_ok = False
    else:
        password_ok = await candidate.acheck_password(user.password)

    if not candidate or not is_active or not password_ok:
        await log_standalone(app_db, action=AuditAction.LOGIN_FAILED,
            details=SessionAuditDetails(event="login_failed"), client_ip=client_ip,
            trace_id=getattr(request.state, "request_id", None))
        try:
            await throttle.record_failure(user.email, client_ip)
        except LoginThrottleUnavailable:
            raise _throttle_unavailable() from None
        raise HTTPException(status_code=400, detail="Invalid email or password")

    async with app_db.get_app_db() as db:
        authenticated_user = (
            await db.execute(select(User).where(User.email == user.email))
        ).scalars().first()
        if not authenticated_user or not authenticated_user.is_active:
            raise HTTPException(status_code=400, detail="Invalid email or password")

        try:
            await throttle.clear_account(user.email)
        except LoginThrottleUnavailable:
            raise _throttle_unavailable() from None

        authenticated_user.last_login_at = db_now()
        
        user_id: int = int(authenticated_user.id)
        
        session_id, refresh_token = await sessions.create_session(
            app_db, user_id, client_ip, request.headers.get("user-agent")
        )
        token = sessions.mint_access(user_id, session_id)

        # Cookie identity includes Path. Expire the old /api-scoped value so
        # upgraded browsers do not continue sending it to every API endpoint.
        _clear_legacy_refresh_cookie(response)
        response.set_cookie(
            key=ACCESS_COOKIE,
            value=token,
            secure=os.getenv("COOKIE_SECURE", "False").lower() == "true",
            samesite="strict",
            httponly=True,
            max_age=sessions.ACCESS_TTL_MINUTES * 60,
            path=ACCESS_COOKIE_PATH,
        )
        response.set_cookie(
            key=REFRESH_COOKIE,
            value=refresh_token,
            secure=os.getenv("COOKIE_SECURE", "False").lower() == "true",
            samesite="strict",
            httponly=True,
            max_age=sessions.REFRESH_TTL_HOURS * 3600,
            path=REFRESH_COOKIE_PATH,
        )
        await app_db.create_login_log(user_id=user_id, client_ip=client_ip)
        await log_standalone(app_db, action=AuditAction.LOGIN, actor=authenticated_user,
            target_type=AuditTarget.USER, target_id=user_id,
            details=SessionAuditDetails(event="login"), client_ip=client_ip,
            trace_id=getattr(request.state, "request_id", None))
        await db.commit()
        
        return {"ok": True}


@router.post("/refresh")
@limiter.limit(config.REFRESH_RATE_LIMITER)
async def refresh_session(
    request: Request,
    response: Response,
    app_db: AppDatabase = Depends(get_app_db),
) -> dict[str, bool]:
    """Rotate the refresh token.

    Rate limited despite being unauthenticated by design: the route sits in
    `skip_auth_paths`, so an invalid token could be retried without bound and
    each attempt cost one or two application-database queries.
    """
    token = request.cookies.get(REFRESH_COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="Refresh token yok")

    rotated = await sessions.rotate_refresh(app_db, token)
    if rotated is None:
        raise HTTPException(status_code=401, detail="Oturum süresi doldu")
    if rotated.get("reuse"):
        raise HTTPException(status_code=401, detail="Güvenlik nedeniyle oturum sonlandırıldı. Tekrar giriş yapın.")

    async with app_db.get_app_db() as db:
        user = await db.get(User, rotated["user_id"])
    if user is None or not getattr(user, "is_active", True):
        await sessions.revoke_session(app_db, rotated["session_id"], "hesap devre dışı")
        raise HTTPException(status_code=401, detail="Hesabınız devre dışı bırakılmış")

    access = sessions.mint_access(rotated["user_id"], rotated["session_id"])
    _clear_legacy_refresh_cookie(response)
    response.set_cookie(
        key=ACCESS_COOKIE, value=access, httponly=True, samesite="strict",
        secure=os.getenv("COOKIE_SECURE", "False").lower() == "true",
        max_age=sessions.ACCESS_TTL_MINUTES * 60, path=ACCESS_COOKIE_PATH,
    )
    response.set_cookie(
        key=REFRESH_COOKIE, value=rotated["refresh_token"], httponly=True,
        samesite="strict", secure=os.getenv("COOKIE_SECURE", "False").lower() == "true",
        max_age=sessions.REFRESH_TTL_HOURS * 3600, path=REFRESH_COOKIE_PATH,
    )
    return {"ok": True}


@router.post("/register")
@limiter.limit(config.RATE_LIMITER)
async def register(
    user: schemas.UserCreate,
    response: Response,
    request: Request,
    app_db: AppDatabase = Depends(get_app_db)
) -> dict[str, Any]:
    """
    New user registration endpoint.
    Registers a new user if the email is not already taken.
    
    Args:
        user: The user registration details payload.
        response: The FastAPI response object.
        request: The FastAPI request object.
        app_db: The application database manager instance.
        
    Returns:
        dict[str, any]: A dictionary indicating success or failure.
    """
    if not config.is_registration_domain_allowed(user.email):
        raise HTTPException(
            status_code=403,
            detail="Bu e-posta alan adıyla kayıt yapılamaz.",
        )

    # The password policy is checked before touching the database so an invalid
    # password is still a clear 400, and no CPU is spent hashing it.
    try:
        validate_password_policy(user.password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    async with app_db.get_app_db() as db:
        result = await db.execute(select(User).where(User.email == user.email))
        existing_user: User | None = result.scalars().first()

        if existing_user:
            # Deliberately indistinguishable from a successful registration.
            # Answering 409 for a known address confirmed which corporate
            # mailboxes exist; activation is an OWNER decision either way, so
            # the caller learns nothing by being told the truth here.
            logger.info("Kayıt denemesi mevcut bir e-posta için yapıldı")
            return {"success": True, "message": _REGISTRATION_ACK}

        new_user: User = User(
            username=user.username,
            email=user.email,
            is_active=not config.REGISTRATION_REQUIRES_ACTIVATION,
        )
        await new_user.aset_password(user.password)

        try:
            db.add(new_user)
            await db.flush()
            await log_in(db, actor=new_user, action=AuditAction.USER_REGISTERED,
                target_type=AuditTarget.USER, target_id=new_user.id,
                details=UserLifecycleAuditDetails(event="registered", source="web"),
                client_ip=request.client.host if request.client else "unknown",
                trace_id=getattr(request.state, "request_id", None))
            await db.commit()
            await db.refresh(new_user)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Database error during registration: {e!s}")
        
        return {"success": True, "message": _REGISTRATION_ACK}


@router.get("/me", response_model=schemas.User)
async def read_users_me(
    current_user: User = Depends(get_current_user),
    app_db: AppDatabase = Depends(get_app_db)
) -> schemas.User:
    """
    Returns current authenticated user information.
    
    Args:
        current_user: The authenticated user instance.
        app_db: The app database manager.
        
    Returns:
        schemas.User: The user details schema.
    """
    async with app_db.get_app_db() as db:
        stmt = select(UserDatabaseAssociation).where(UserDatabaseAssociation.user_id == current_user.id)
        res = await db.execute(stmt)
        assocs = res.scalars().all()
        is_admin = any_admin(assocs)

    return schemas.User(
        username=current_user.username,
        is_admin=is_admin,
        is_platform_owner=bool(current_user.is_platform_owner),
    )


@router.post("/me/password", response_model=schemas.PasswordChangeResponse)
@limiter.limit(config.RATE_LIMITER)
async def change_password(
    payload: schemas.PasswordChangeRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    app_db: AppDatabase = Depends(get_app_db),
) -> dict[str, Any]:
    """
    Changes the caller's own password.

    There was previously no way to change a password from inside the
    application — no change endpoint and no reset — so a password known to be
    compromised could not be replaced at all. `AuditAction.PASSWORD_CHANGED`
    existed with no call site.

    The current password is required, so someone holding a stolen session
    cannot lock the real owner out. On success every *other* session for the
    user is revoked: a password change is the standard way to end sessions an
    attacker may hold, and keeping this one avoids logging the user out of the
    request they are making.
    """
    # Both hashes run on a worker thread; see `User.acheck_password`.
    if not await current_user.acheck_password(payload.current_password):
        logger.warning("Şifre değiştirme reddedildi: mevcut şifre hatalı")
        raise HTTPException(status_code=400, detail="Mevcut şifre hatalı.")

    if payload.new_password == payload.current_password:
        raise HTTPException(
            status_code=400, detail="Yeni şifre mevcut şifreyle aynı olamaz."
        )

    try:
        validate_password_policy(payload.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    new_hash = await anyio.to_thread.run_sync(hash_password, payload.new_password)
    current_session_id = _current_session_id(request)

    async with app_db.get_app_db() as db:
        async with db.begin():
            user = await db.get(User, current_user.id, with_for_update=True)
            if user is None:
                raise HTTPException(status_code=401, detail="Invalid token")
            user.password = new_hash

            revoked = await db.execute(
                update(UserSession)
                .where(
                    UserSession.user_id == user.id,
                    UserSession.revoked_at.is_(None),
                    UserSession.id != current_session_id,
                )
                .values(
                    revoked_at=db_now(),
                    revoked_reason="password changed",
                )
            )
            revoked_count = revoked.rowcount or 0

            # Same transaction as the hash write: an audit row must not claim a
            # change that rolled back. Details never carry a password or hash.
            await log_in(
                db,
                actor=user,
                action=AuditAction.PASSWORD_CHANGED,
                target_type=AuditTarget.USER,
                target_id=user.id,
                details=PasswordChangeAuditDetails(revoked_sessions=revoked_count),
                client_ip=request.client.host if request.client else None,
                trace_id=getattr(request.state, "request_id", None),
            )

    return {
        "success": True,
        "message": "Şifreniz güncellendi. Diğer oturumlarınız sonlandırıldı.",
        "revoked_sessions": revoked_count,
    }


@router.post("/logout")
async def logout(
    response: Response,
    request: Request,
    current_user: User = Depends(get_current_user),
    app_db: AppDatabase = Depends(get_app_db),
) -> dict[str, str]:
    """
    User logout endpoint.
    Clears auth cookies, revokes the current session, and records the logout.
    
    Args:
        response: The FastAPI response object.
        request: The FastAPI request object.
        current_user: The authenticated user instance.
        app_db: The application database manager instance.
        db_provider: The database provider instance.
        
    Returns:
        dict[str, str]: A dictionary with success status.
    """
    # Revoke the server-side session. The old JTI blacklist was removed with
    # OQ-2026-014: `mint_access` never issued a `jti`, so the table was never
    # written and the check never fired. `UserSession` is the real revocation
    # record and every request already consults it.
    token = request.cookies.get(ACCESS_COOKIE)
    if token:
        try:
            payload = jwt.decode(token, config.SECRET_KEY, algorithms=[config.ALGORITHM])
            if payload.get("sid"):
                await sessions.revoke_session(app_db, int(payload["sid"]), "logout")
        except Exception as exc:
            logger.warning("Çıkış sırasında oturum iptal edilemedi: %s", type(exc).__name__)

    # Clear token from cookie
    response.delete_cookie(
        key=ACCESS_COOKIE,
        secure=os.getenv("COOKIE_SECURE", "False").lower() == "true",
        samesite="strict",
        httponly=True
    )
    response.delete_cookie(
        key=REFRESH_COOKIE,
        secure=os.getenv("COOKIE_SECURE", "False").lower() == "true",
        samesite="strict",
        httponly=True,
        path=REFRESH_COOKIE_PATH,
    )
    _clear_legacy_refresh_cookie(response)
    
    await app_db.update_login_log(user_id=current_user.id)
    await log_standalone(app_db, action=AuditAction.LOGOUT, actor=current_user,
        target_type=AuditTarget.USER, target_id=current_user.id,
        details=SessionAuditDetails(event="logout"),
        client_ip=request.client.host if request.client else "unknown",
        trace_id=getattr(request.state, "request_id", None))

    return {"message": "Successfully logged out"}
