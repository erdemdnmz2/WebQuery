"""
WebQuery API - New Modular Architecture
Clean dependency injection with AppDatabase and DatabaseProvider
"""
import os
from dotenv import load_dotenv
import asyncio

# Load .env file (you can use .env.production for production)
env_file = os.getenv("ENV_FILE", ".env")
load_dotenv(env_file)

from fastapi import FastAPI
from contextlib import asynccontextmanager
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import uvicorn
from starlette.middleware.cors import CORSMiddleware
from cryptography.fernet import Fernet
from sqlalchemy import text

from app_database import AppDatabase
from database_provider import DatabaseProvider
from session import SessionCache
from middlewares import AuthMiddleware

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
        await app.state.app_db.create_tables()
        print("✓ Tables created/checked")
    except Exception as e:
        print(f"\n❌ FATAL: AppDatabase connection error!")
        print(f"   Error: {type(e).__name__}: {e}")
        print(f"   Please check the APP_DATABASE_URL environment variable")
        print(f"   Application cannot start!\n")
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
        print("✓ DatabaseProvider ready and db_info loaded")
    except Exception as e:
        print(f"\n❌ FATAL: DatabaseProvider initialization error!")
        print(f"   Error: {type(e).__name__}: {e}")
        print(f"   Please check the SQL_SERVER_NAMES environment variable and SQL Server connections")
        print(f"   Application cannot start!\n")
        # Cleanup
        await app.state.app_db.app_engine.dispose()
        raise SystemExit(1)

    app.state.fernet = Fernet(Fernet.generate_key())
    print("✓ Fernet encryption ready")

    app.state.session_cache = SessionCache(fernet=app.state.fernet)
    print("✓ Session cache ready")

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

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(AuthMiddleware)
app.add_middleware(SlowAPIMiddleware)

# Configure CORS securely from environment variable
allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "")
if allowed_origins_env:
    allowed_origins = [origin.strip() for origin in allowed_origins_env.split(",")]
else:
    # Default to localhost for development if nothing is provided
    allowed_origins = ["http://localhost", "http://localhost:80", "http://localhost:3000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True, # Often needed for auth cookies if used later
    allow_methods=["*"],
    allow_headers=["*"],
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
        port=int(os.getenv("PORT", 8080)),
        workers=int(os.getenv("WORKERS", 1)),
        reload=True
    )