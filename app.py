"""
WebQuery API - Yeni Modüler Mimari
AppDatabase ve DatabaseProvider ile temiz dependency injection
"""
from fastapi import FastAPI
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import uvicorn

from app_database.app_database import AppDatabase
from database_provider import DatabaseProvider
from session import SessionCache

from middlewares import AuthMiddleware

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Uygulama başlatılırken:
    - AppDatabase (uygulama DB) oluşturulur
    - DatabaseProvider (kullanıcı DB'leri) oluşturulur ve initialize edilir
    - Her ikisi de app.state'e konur
    
    Kapatılırken:
    - Tüm engine'ler temizlenir
    """
    # Startup
    try:
        print("🚀 Uygulama başlatılıyor...")
        
        app.state.app_db = AppDatabase()
        print("✓ AppDatabase hazır")
        
        app.state.db_provider = DatabaseProvider()
        await app.state.db_provider.get_db_info()
        print("✓ DatabaseProvider hazır ve db_info yüklendi")
        
        
        app.state.session_cache = SessionCache()
        print("✓ Session cache hazır")

        app.state.workspace_service
        
        print("Tüm servisler başarıyla başlatıldı\n")
        
        yield
        
    except Exception as e:
        print(f"Uygulama başlatma hatası: {e}")
        raise  
    
    finally:
        print("\nUygulama kapatılıyor...")
        
        try:
            if hasattr(app.state, 'db_provider') and app.state.db_provider:
                await app.state.db_provider.close_engines()
                print("✓ DatabaseProvider bağlantıları kapatıldı")
        except Exception as e:
            print(f"DatabaseProvider kapatma hatası: {e}")
        
        try:
            if hasattr(app.state, 'app_db') and app.state.app_db:
                await app.state.app_db.app_engine.dispose()
                print("✓ AppDatabase bağlantısı kapatıldı")
        except Exception as e:
            print(f"AppDatabase kapatma hatası: {e}")
        
        print("Kapatma işlemi tamamlandı")

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

from authentication.router import router as auth_router
app.include_router(auth_router, tags=["Authentication"])

from query_execution.router import router as query_router
app.include_router(query_router, tags=["Query Execution"])

from admin.router import router as admin_router
app.include_router(admin_router, tags=["Admin"])

from workspaces.router import router as workspace_router
app.include_router(workspace_router, tags=["Workspace"])

from static_files.router import router as static_router
app.include_router(static_router, tags=["Static Files"])

@app.get("/health")
async def health_check():
    """Sağlık kontrolü endpoint'i"""
    return {
        "status": "healthy",
        "app_db": "connected" if app.state.app_db else "disconnected",
        "db_provider": "connected" if app.state.db_provider else "disconnected"
    }

if __name__ == "__main__":
    uvicorn.run(
        "app_new:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
