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
from cryptography.fernet import Fernet
import uvicorn

# Yeni mimari sınıfları
from app_database.app_database import AppDatabase
from database_provider import DatabaseProvider

# Middleware
from middlewares import AuthMiddleware

# Session cache için
session_cache = {}
session_key = Fernet.generate_key()
fernet_instance = Fernet(session_key)


# ========================================
# Lifespan: Uygulama Başlatma ve Kapatma
# ========================================
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
        
        # AppDatabase instance'ı oluştur (uygulama kendi DB'si)
        app.state.app_db = AppDatabase()
        print("✓ AppDatabase hazır")
        
        # DatabaseProvider instance'ı oluştur (kullanıcı hedef DB'leri)
        app.state.db_provider = DatabaseProvider()
        await app.state.db_provider.get_db_info()
        print("✓ DatabaseProvider hazır ve db_info yüklendi")
        
        # Session cache ve fernet instance'larını state'e koy
        app.state.session_cache = session_cache
        app.state.fernet = fernet_instance
        print("✓ Session cache hazır")
        
        print("✅ Tüm servisler başarıyla başlatıldı\n")
        
        yield
        
    except Exception as e:
        print(f"❌ Uygulama başlatma hatası: {e}")
        raise  # Uygulama başlamasın
    
    finally:
        # Graceful shutdown - her durumda çalışır
        print("\n🛑 Uygulama kapatılıyor...")
        
        try:
            # DatabaseProvider engine'lerini kapat
            if hasattr(app.state, 'db_provider') and app.state.db_provider:
                await app.state.db_provider.close_engines()
                print("✓ DatabaseProvider bağlantıları kapatıldı")
        except Exception as e:
            print(f"⚠️ DatabaseProvider kapatma hatası: {e}")
        
        try:
            # AppDatabase engine'ini kapat
            if hasattr(app.state, 'app_db') and app.state.app_db:
                await app.state.app_db.app_engine.dispose()
                print("✓ AppDatabase bağlantısı kapatıldı")
        except Exception as e:
            print(f"⚠️ AppDatabase kapatma hatası: {e}")
        
        print("✅ Kapatma işlemi tamamlandı")


# ========================================
# FastAPI Uygulaması
# ========================================
app = FastAPI(
    title="WebQuery API",
    description="Modular SQL Query Execution Platform",
    version="2.0.0",
    lifespan=lifespan
)


# ========================================
# Rate Limiter
# ========================================
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# ========================================
# Middleware
# ========================================
app.add_middleware(AuthMiddleware)


# ========================================
# Router'ları Include Et
# ========================================
# Authentication Router
from authentication.router import router as auth_router
app.include_router(auth_router, tags=["Authentication"])

# Query Execution Router
from query_execution.router import router as query_router
app.include_router(query_router, tags=["Query Execution"])

# TODO: Admin router eklenecek
# from admin.router import router as admin_router
# app.include_router(admin_router, tags=["Admin"])

# TODO: Workspace router eklenecek
# from workspace.router import router as workspace_router
# app.include_router(workspace_router, tags=["Workspace"])


# ========================================
# HTML Sayfaları (Statik)
# ========================================
@app.get("/", response_class=FileResponse)
def homepage():
    return FileResponse("templates/home.html")


@app.get("/login", response_class=FileResponse)
def login_page():
    return FileResponse("templates/login.html")


@app.get("/register", response_class=FileResponse)
def register_page():
    return FileResponse("templates/register.html")


@app.get("/admin", response_class=FileResponse)
def admin_page():
    return FileResponse("templates/admin.html")


@app.get("/index", response_class=FileResponse)
def index_page():
    return FileResponse("templates/index.html")


@app.get("/home", response_class=FileResponse)
def home_page():
    return FileResponse("templates/index.html")


# ========================================
# Health Check
# ========================================
@app.get("/health")
async def health_check():
    """Sağlık kontrolü endpoint'i"""
    return {
        "status": "healthy",
        "app_db": "connected" if app.state.app_db else "disconnected",
        "db_provider": "connected" if app.state.db_provider else "disconnected"
    }


# ========================================
# Uygulama Çalıştırma
# ========================================
if __name__ == "__main__":
    uvicorn.run(
        "app_new:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
