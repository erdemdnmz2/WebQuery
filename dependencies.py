"""
Ortak Dependency Injection Fonksiyonları
Tüm router'lar bu fonksiyonları kullanarak app.state'ten instance'ları alır
"""
from fastapi import Request
from cryptography.fernet import Fernet

from app_database.app_database import AppDatabase
from database_provider import DatabaseProvider
from query_execution.services import QueryService

def get_app_db(request: Request) -> AppDatabase:
    """
    AppDatabase instance'ını döndürür.
    Kullanım: app_db: AppDatabase = Depends(get_app_db)
    """
    return request.app.state.app_db


def get_db_provider(request: Request) -> DatabaseProvider:
    """
    DatabaseProvider instance'ını döndürür.
    Kullanım: db_provider: DatabaseProvider = Depends(get_db_provider)
    """
    return request.app.state.db_provider


from session.session_cache import SessionCache

def get_session_cache(request: Request) -> SessionCache:
    """
    SessionCache instance'ını döndürür (kullanıcı şifrelerini geçici saklar).
    Kullanım: session_cache: SessionCache = Depends(get_session_cache)
    """
    return request.app.state.session_cache


def get_fernet(request: Request) -> Fernet:
    """
    Fernet şifreleme instance'ını döndürür.
    Kullanım: fernet: Fernet = Depends(get_fernet)
    """
    return request.app.state.fernet

def get_query_service(request: Request) -> QueryService:
    """
    QueryService instance'ını döndürür.
    Kullanım: query_service: QueryService = Depends(get_query_service)
    """
    app_db = get_app_db(request)
    db_provider = get_db_provider(request)
    return QueryService(database_provider=db_provider, app_db=app_db)
