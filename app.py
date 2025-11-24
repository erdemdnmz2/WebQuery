"""
WebQuery API - Yeni Modüler Mimari
AppDatabase ve DatabaseProvider ile temiz dependency injection
"""
import os
from dotenv import load_dotenv

# .env dosyasını yükle (production için .env.production kullanabilirsiniz)
env_file = os.getenv("ENV_FILE", ".env")
load_dotenv(env_file)

from fastapi import FastAPI
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import uvicorn
from starlette.middleware.cors import CORSMiddleware
from cryptography.fernet import Fernet
from sqlalchemy import text

from app_database.app_database import AppDatabase
from database_provider import DatabaseProvider
from session import SessionCache
from middlewares import AuthMiddleware

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup: initialize AppDatabase, DatabaseProvider, Fernet, and SessionCache
    Teardown: close engines and dispose resources
    """
    # Startup
    print("🚀 Uygulama başlatılıyor...")
    
    try:
        app.state.app_db = AppDatabase()
        # Gerçek bağlantı testi
        async with app.state.app_db.app_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        print("✓ AppDatabase bağlantısı başarılı")
        await app.state.app_db.create_tables()
        print("✓ Tablolar oluşturuldu/kontrol edildi")
    except Exception as e:
        print(f"\n❌ FATAL: AppDatabase bağlantı hatası!")
        print(f"   Hata: {type(e).__name__}: {e}")
        print(f"   Lütfen APP_DATABASE_URL environment variable'ını kontrol edin")
        print(f"   Uygulama başlatılamıyor!\n")
        await app.state.app_db.app_engine.dispose() if hasattr(app.state, 'app_db') else None
        raise SystemExit(1)

    try:
        app.state.db_provider = DatabaseProvider()
        db_info = await app.state.app_db.get_db_info()
        
        # Validate db_info
        if not db_info:
            print("\n⚠️  WARNING: Databases tablosu boş!")
            print("   Lütfen Databases tablosuna kayıt ekleyin.")
            print("   Örnek: INSERT INTO Databases (servername, database_name, technology)")
            print("          VALUES ('localhost', 'mydb', 'mssql');")
            print("   Uygulama çalışacak ancak hiçbir veritabanına bağlanamayacak.\n")
        else:
            print(f"✓ {len(db_info)} server yapılandırması yüklendi:")
            for server, info in db_info.items():
                db_count = len(info.get('databases', []))
                tech = info.get('technology', 'unknown')
                print(f"  • {server}: {db_count} database ({tech.upper()})")
        
        app.state.db_provider.set_db_info(db_info)
        print("✓ DatabaseProvider hazır ve db_info yüklendi")
    except Exception as e:
        print(f"\n❌ FATAL: DatabaseProvider başlatma hatası!")
        print(f"   Hata: {type(e).__name__}: {e}")
        print(f"   Lütfen Databases tablosunu kontrol edin")
        print(f"   Uygulama başlatılamıyor!\n")
        # Cleanup
        await app.state.app_db.app_engine.dispose()
        raise SystemExit(1)

    app.state.fernet = Fernet(Fernet.generate_key())
    print("✓ Fernet encryption hazır")

    app.state.session_cache = SessionCache(fernet=app.state.fernet)
    print("✓ Session cache hazır")

    print("Tüm servisler başarıyla başlatıldı\n")

    try:
        yield
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
app.add_middleware(SlowAPIMiddleware)

#TODO burayı ayarla
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
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

from static_files.router import router as static_router
app.include_router(static_router, tags=["Static Files"])

@app.get("/health")
async def health_check():
    """Sağlık kontrolü endpoint'i"""
    return {
        "status": "healthy",
        "app_db": "connected" if getattr(app.state, 'app_db', None) else "disconnected",
        "db_provider": "connected" if getattr(app.state, 'db_provider', None) else "disconnected"
    }

if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
