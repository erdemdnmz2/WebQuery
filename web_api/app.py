"""
WebQuery API - New Modular Architecture
Clean dependency injection with AppDatabase and DatabaseProvider
"""
import asyncio
import os

from dotenv import load_dotenv

# Load .env file (you can use .env.production for production)
env_file = os.getenv("ENV_FILE", ".env")
load_dotenv(env_file)

from common.logging_config import setup_logging

setup_logging()

import logging
from contextlib import asynccontextmanager, suppress

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import text
from starlette.middleware.cors import CORSMiddleware

from app_database import AppDatabase
from authentication.login_throttle import LoginThrottleUnavailable, RedisLoginThrottle
from common.config_guard import verify_startup_config
from common.errors import redact_passwords
from common.exceptions import BaseServiceException
from common.limiter import limiter
from common.schema_guard import verify_schema
from database_provider import DatabaseProvider
from middlewares import AuthMiddleware, TrustedProxyMiddleware
from middlewares.trace_middleware import TraceMiddleware
from owner.bootstrap import ensure_active_owner
from slack_integration import SlackListener

logger = logging.getLogger(__name__)


def _log_slack_listener_exit(task: "asyncio.Task[None]") -> None:
    """Surface a Slack listener that dies on its own.

    Without this the socket-mode connection could fail permanently and the only
    symptom would be approvals silently never arriving.
    """
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        logger.error(
            "Slack dinleyicisi beklenmedik şekilde sonlandı: %s; "
            "Slack onay akışı çalışmayacak",
            type(exc).__name__,
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manages application startup and shutdown lifecycle.
    """
    # Startup
    verify_startup_config()
    logger.info("Uygulama başlatılıyor")

    try:
        app.state.login_throttle = RedisLoginThrottle.from_environment()
        await app.state.login_throttle.ping()
        logger.info("Redis giriş kısıtlayıcı bağlantısı doğrulandı")
    except (LoginThrottleUnavailable, ValueError) as exc:
        logger.critical(
            "Redis giriş kısıtlayıcı bağlantısı kurulamadı: %s; uygulama başlatılmayacak",
            type(exc).__name__,
        )
        raise SystemExit(1) from exc
    
    try:
        app.state.app_db = AppDatabase()
        # Real connection test
        async with app.state.app_db.app_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            # Migrations have already run in entrypoint.sh by this point. An
            # install bootstrapped by create_all() before Alembic existed never
            # received the baseline's indexes and constraints, and no revision
            # backfills them on its own — so the schema is verified here rather
            # than trusted. verify_schema raises SystemExit, which is a
            # BaseException and deliberately passes through the handler below.
            await conn.run_sync(verify_schema)
        logger.info("Uygulama veritabanı bağlantısı ve şema doğrulandı")
        await ensure_active_owner(app.state.app_db)
        logger.info("Aktif platform OWNER doğrulandı")
        # Schema is managed by Alembic (`alembic upgrade head`, run in
        # entrypoint.sh before this process starts) — see
        # docs/adr/ADR-0001-schema-migrations-alembic.md. Two instances
        # calling create_all() concurrently on startup raced on schema
        # changes and couldn't add columns to existing tables.
    except Exception as e:
        logger.critical(
            "Uygulama veritabanı başlatılamadı: %s; APP_DATABASE_URL ayarını kontrol edin",
            type(e).__name__,
        )
        await app.state.app_db.app_engine.dispose() if hasattr(app.state, 'app_db') else None
        raise SystemExit(1)
    
    try:
        app_db = app.state.app_db
        # Start Slack Listener (Socket Mode)
        app.state.slack_listener = SlackListener(app_db=app_db)
        slack_listener = app.state.slack_listener
        # Held on app.state, not dropped on the floor: asyncio keeps only a
        # weak reference to a running task, so an unreferenced one can be
        # garbage-collected mid-flight and the Slack approval channel would
        # stop working with nothing in the logs to say why. The reference also
        # gives shutdown something to cancel.
        slack_task = asyncio.create_task(slack_listener.start())
        slack_task.add_done_callback(_log_slack_listener_exit)
        app.state.slack_task = slack_task

    except Exception as e:
        logger.warning(
            "Slack entegrasyonu başlatılamadı: %s; Slack özellikleri devre dışı kalacak",
            type(e).__name__,
        )

    try:
        app.state.db_provider = DatabaseProvider()
        db_info = await app.state.app_db.get_db_info()
        app.state.db_provider.set_db_info(db_info)
        await app.state.db_provider.start_cache_loop()
        logger.info("Hedef veritabanı sağlayıcısı ve engine cache başlatıldı")
    except Exception as e:
        logger.critical(
            "Hedef veritabanı sağlayıcısı başlatılamadı: %s; bağlantı yapılandırmasını kontrol edin",
            type(e).__name__,
        )
        # Cleanup
        await app.state.app_db.app_engine.dispose()
        raise SystemExit(1)

    # Initialize AppContext to hold singleton instances of all stateless services
    try:
        from dependencies import AppContext
        app.state.context = AppContext(
            app_db=app.state.app_db,
            db_provider=app.state.db_provider
        )
        logger.info("Uygulama bağlamı başlatıldı")
    except Exception as e:
        logger.critical("Uygulama bağlamı başlatılamadı: %s", type(e).__name__)
        await app.state.app_db.app_engine.dispose()
        raise SystemExit(1)

    logger.info("Tüm servisler başlatıldı")

    try:
        yield
    finally:
        logger.info("Uygulama kapatılıyor")
        slack_task = getattr(app.state, "slack_task", None)
        if slack_task is not None and not slack_task.done():
            slack_task.cancel()
            with suppress(asyncio.CancelledError):
                await slack_task
            logger.info("Slack dinleyicisi durduruldu")
        if getattr(app.state, "login_throttle", None):
            await app.state.login_throttle.close()
            logger.info("Redis giriş kısıtlayıcı bağlantısı kapatıldı")
        try:
            if hasattr(app.state, 'db_provider') and app.state.db_provider:
                await app.state.db_provider.close_engines()
                logger.info("Hedef veritabanı bağlantıları kapatıldı")
        except Exception as e:
            logger.error("Hedef veritabanı sağlayıcısı kapatılamadı: %s", type(e).__name__)
        try:
            if hasattr(app.state, 'app_db') and app.state.app_db:
                await app.state.app_db.app_engine.dispose()
                logger.info("Uygulama veritabanı bağlantısı kapatıldı")
        except Exception as e:
            logger.error("Uygulama veritabanı bağlantısı kapatılamadı: %s", type(e).__name__)
        logger.info("Uygulama kapatma işlemi tamamlandı")

app = FastAPI(
    title="WebQuery API",
    description="Modular SQL Query Execution Platform",
    version="2.0.0",
    lifespan=lifespan
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(AuthMiddleware)
app.add_middleware(TraceMiddleware)
app.add_middleware(SlowAPIMiddleware)

cors_origins_str = os.getenv("CORS_ALLOWED_ORIGINS", "*")
cors_origins = [origin.strip() for origin in cors_origins_str.split(",")] if cors_origins_str else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Added last, so it is the outermost middleware and runs first. Everything that
# reads the client address downstream — SlowAPIMiddleware's rate limit key, the
# login throttle's IP bucket, and every audit `client_ip` — must see the address
# this resolves, not the reverse proxy's own.
app.add_middleware(TrustedProxyMiddleware)

@app.exception_handler(BaseServiceException)
async def service_exception_handler(request: Request, exc: BaseServiceException):
    exception_logger = logging.getLogger("web_api.exception")
    if exc.original_exception:
        exception_logger.error(
            "Service exception [%s] at %s: %s; underlying %s: %s",
            exc.code,
            request.url.path,
            exc.message,
            type(exc.original_exception).__name__,
            redact_passwords(str(exc.original_exception)),
        )
    else:
        exception_logger.warning(
            "Service exception [%s] at %s: %s", exc.code, request.url.path, exc.message
        )
    
    trace_id = getattr(request.state, "request_id", "-")
    body = {
        "success": False,
        "error_code": exc.code,
        "message": exc.message,
        "error": exc.message,  # Backward compatibility
        "trace_id": trace_id
    }
    # A few errors carry a list the caller must resolve before retrying; see
    # BaseServiceException.response_context.
    context = exc.response_context()
    if context:
        body.update(context)
    return JSONResponse(status_code=exc.status_code, content=body)

from authentication.router import router as auth_router

app.include_router(auth_router, tags=["Authentication"])

from query_execution.router import router as query_router

app.include_router(query_router, tags=["Query Execution"])

from admin.router import router as admin_router

app.include_router(admin_router, tags=["Admin"])

from owner.router import router as owner_router

app.include_router(owner_router, tags=["Owner"])

from workspaces.router import router as workspace_router

app.include_router(workspace_router, tags=["Workspace"])

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "app_db": "connected" if getattr(app.state, 'app_db', None) else "disconnected",
        "db_provider": "connected" if getattr(app.state, 'db_provider', None) else "disconnected"
    }

if __name__ == "__main__":
    # DEBUG defaults to false: with reload=True uvicorn ignores `workers`
    # entirely and watches the filesystem, which is not a production server.
    # Opting into auto-reload now has to be explicit.
    debug = os.getenv("DEBUG", "false").strip().lower() == "true"
    trusted_proxies = os.getenv("TRUSTED_PROXY_IPS", "").strip()

    uvicorn.run(
        "app:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8080")),
        workers=int(os.getenv("WORKERS", "1")),
        reload=debug,
        # Defence in depth alongside TrustedProxyMiddleware, which does the same
        # resolution inside the app so it also holds under gunicorn or the
        # uvicorn CLI. Never "*": that lets any client forge its own address.
        proxy_headers=bool(trusted_proxies),
        forwarded_allow_ips=trusted_proxies or None,
    )
