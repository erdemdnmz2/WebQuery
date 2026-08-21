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
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import text
from starlette.middleware.cors import CORSMiddleware

from app_database import AppDatabase
from common.exceptions import BaseServiceException
from common.limiter import limiter
from database_provider import DatabaseProvider
from middlewares import AuthMiddleware
from middlewares.trace_middleware import TraceMiddleware
from slack_integration import SlackListener


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manages application startup and shutdown lifecycle.
    """
    # Startup
    print("🚀 Application starting...")
    
    try:
        app.state.app_db = AppDatabase()
        # Real connection test
        async with app.state.app_db.app_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        print("✓ AppDatabase connection successful")
        # Schema is managed by Alembic (`alembic upgrade head`, run in
        # entrypoint.sh before this process starts) — see
        # docs/adr/ADR-0001-schema-migrations-alembic.md. Two instances
        # calling create_all() concurrently on startup raced on schema
        # changes and couldn't add columns to existing tables.
    except Exception as e:
        print("\n❌ FATAL: AppDatabase connection error!")
        print(f"   Error: {type(e).__name__}: {e}")
        print("   Please check the APP_DATABASE_URL environment variable")
        print("   Application cannot start!\n")
        await app.state.app_db.app_engine.dispose() if hasattr(app.state, 'app_db') else None
        raise SystemExit(1)
    
    try:
        app_db = app.state.app_db
        # Start Slack Listener (Socket Mode)
        app.state.slack_listener = SlackListener(app_db=app_db)
        slack_listener = app.state.slack_listener
        asyncio.create_task(slack_listener.start())

    except Exception as e:
        print(f"⚠️ Slack integration could not be started: {e}")
        print("   Slack features will be disabled, but the application will continue to run.")

    try:
        app.state.db_provider = DatabaseProvider()
        db_info = await app.state.app_db.get_db_info()
        app.state.db_provider.set_db_info(db_info)
        await app.state.db_provider.start_cache_loop()
        print("✓ DatabaseProvider ready, db_info loaded, and cache loop started")
    except Exception as e:
        print("\n❌ FATAL: DatabaseProvider initialization error!")
        print(f"   Error: {type(e).__name__}: {e}")
        print("   Please check the SQL_SERVER_NAMES environment variable and SQL Server connections")
        print("   Application cannot start!\n")
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
        print("✓ AppContext initialized successfully")
    except Exception as e:
        print(f"\n❌ FATAL: AppContext initialization error: {e}")
        await app.state.app_db.app_engine.dispose()
        raise SystemExit(1)

    print("All services started successfully\n")

    try:
        yield
    finally:
        print("\nApplication shutting down...")
        try:
            if hasattr(app.state, 'db_provider') and app.state.db_provider:
                await app.state.db_provider.close_engines()
                print("✓ DatabaseProvider connections closed")
        except Exception as e:
            print(f"DatabaseProvider shutdown error: {e}")
        try:
            if hasattr(app.state, 'app_db') and app.state.app_db:
                await app.state.app_db.app_engine.dispose()
                print("✓ AppDatabase connection closed")
        except Exception as e:
            print(f"AppDatabase shutdown error: {e}")
        print("Shutdown complete")

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

@app.exception_handler(BaseServiceException)
async def service_exception_handler(request: Request, exc: BaseServiceException):
    logger = logging.getLogger("web_api.exception")
    if exc.original_exception:
        logger.error(
            f"Service Exception [{exc.code}] on {request.url.path}: {exc.message} - "
            f"Underlying Error: {type(exc.original_exception).__name__}: {exc.original_exception}",
            exc_info=exc.original_exception
        )
    else:
        logger.warning(f"Service Exception [{exc.code}] on {request.url.path}: {exc.message}")
    
    trace_id = getattr(request.state, "request_id", "-")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error_code": exc.code,
            "message": exc.message,
            "error": exc.message,  # Backward compatibility
            "trace_id": trace_id
        }
    )

from authentication.router import router as auth_router

app.include_router(auth_router, tags=["Authentication"])

from query_execution.router import router as query_router

app.include_router(query_router, tags=["Query Execution"])

from admin.router import router as admin_router

app.include_router(admin_router, tags=["Admin"])

from workspaces.router import router as workspace_router

app.include_router(workspace_router, tags=["Workspace"])

# from static_files.router import router as static_router
# app.include_router(static_router, tags=["Static Files"])

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "app_db": "connected" if getattr(app.state, 'app_db', None) else "disconnected",
        "db_provider": "connected" if getattr(app.state, 'db_provider', None) else "disconnected"
    }

if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8080")),
        workers=int(os.getenv("WORKERS", "1")),
        reload=os.getenv("DEBUG", "True").lower() == "true"
    )