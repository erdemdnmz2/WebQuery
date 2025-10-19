"""
Query Execution Router
SQL query çalıştırma endpoint'leri
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import List

from query_execution import config
from query_execution import models as query_models
from query_execution.services import QueryService
from authentication.services import get_current_user, is_session_valid
from dependencies import get_app_db, get_db_provider, get_session_cache
from app_database.app_database import AppDatabase
from database_provider import DatabaseProvider
from app_database.models import User

router = APIRouter(prefix="/api")


def get_query_service(
    app_db: AppDatabase = Depends(get_app_db),
    db_provider: DatabaseProvider = Depends(get_db_provider)
) -> QueryService:
    """QueryService instance'ını döndürür"""
    return QueryService(database_provider=db_provider, app_db=app_db)


@router.post("/execute_query", response_model=query_models.SQLResponse)
async def execute_query(
    query_request: query_models.SQLQuery,
    current_user: User = Depends(get_current_user),
    query_service: QueryService = Depends(get_query_service),
    session_cache: dict = Depends(get_session_cache)
):
    """
    Tek bir SQL query'sini çalıştırır
    
    1. Session kontrolü (kullanıcının session'ı hala geçerli mi?)
    2. Query'yi çalıştır
    3. Sonucu döndür
    """
    # Session kontrolü
    if current_user.id in session_cache:
        if not is_session_valid(current_user.id, session_cache):
            raise HTTPException(status_code=401, detail="Session expired")
    
    # Query'yi çalıştır
    result = await query_service.execute_query(
        query=query_request.query,
        user=current_user,
        server_name=query_request.servername,
        database_name=query_request.database_name
    )
    
    return result


@router.post("/multiple_query", response_model=query_models.MultipleQueryResponse)
async def multiple_query(
    request: query_models.MultipleQueryRequest,
    current_user: User = Depends(get_current_user),
    query_service: QueryService = Depends(get_query_service),
    session_cache: dict = Depends(get_session_cache)
):
    """
    Birden fazla SQL query'sini sırayla çalıştırır
    
    1. Session kontrolü
    2. Query count kontrolü (max: config.MULTIPLE_QUERY_COUNT)
    3. Her query'yi sırayla çalıştır
    4. Tüm sonuçları döndür
    """
    # Session kontrolü
    if current_user.id in session_cache:
        if not is_session_valid(current_user.id, session_cache):
            raise HTTPException(status_code=401, detail="Session expired")
    
    # Query count kontrolü
    if len(request.execution_info) > config.MULTIPLE_QUERY_COUNT:
        raise HTTPException(
            status_code=400,
            detail=f"Too many queries. Maximum: {config.MULTIPLE_QUERY_COUNT}"
        )
    
    results = []
    
    for execution_info in request.execution_info:
        result = await query_service.execute_query(
            query=execution_info.query,
            user=current_user,
            server_name=execution_info.servername,
            database_name=execution_info.database_name
        )
        results.append(result)
    
    return query_models.MultipleQueryResponse(results=results)


@router.get("/database_information", response_model=query_models.DatabaseInformationResponse)
async def get_database_information(
    current_user: User = Depends(get_current_user),
    db_provider: DatabaseProvider = Depends(get_db_provider)
):
    """
    Kullanıcının erişebildiği veritabanlarının listesini döndürür
    
    Returns:
        {servername: [database_names]} formatında dictionary
    """
    # Kullanıcı engine cache'te yoksa
    if current_user.id not in db_provider.engine_cache:
        raise HTTPException(
            status_code=404,
            detail="No database connections found for user"
        )
    
    # Kullanıcının erişebildiği database'leri al
    db_info = db_provider.get_db_info_by_user_id(current_user.id)
    
    return {"db_info": db_info}
