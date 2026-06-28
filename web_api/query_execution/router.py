"""
Query Execution Router Module
FastAPI router for single and multiple SQL query execution.
All routes are strictly typed and documented.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from typing import List, Any
from common.limiter import limiter

from query_execution import config
from query_execution import schemas as query_models
from query_execution.services import QueryService
from authentication.services import get_current_user
from dependencies import get_db_provider, get_query_service
from database_provider import DatabaseProvider
from app_database.models import User

router = APIRouter(prefix="/api")

# Using centralized limiter


@router.post("/execute_query", response_model=query_models.SQLResponse)
@limiter.limit(config.RATE_LIMITER)
async def execute_query(
    request: Request,
    query_request: query_models.SQLQuery,
    current_user: User = Depends(get_current_user),
    query_service: QueryService = Depends(get_query_service)
) -> dict[str, Any]:
    """
    Executes a single SQL query via the query execution service.
    
    Args:
        request: The FastAPI request object.
        query_request: The SQL query execution request payload.
        current_user: The authenticated user instance.
        query_service: The query execution service instance.
        
    Returns:
        dict[str, Any]: The query execution results or error response.
    """
    result: dict[str, Any] = await query_service.execute_query(
        query=query_request.query,
        user=current_user,
        server_name=query_request.servername,
        database_name=query_request.database_name,
        ad_hoc_mask_columns=query_request.ad_hoc_mask_columns
    )
    return result


@router.post("/multiple_query", response_model=query_models.MultipleQueryResponse)
async def multiple_query(
    request: query_models.MultipleQueryRequest,
    current_user: User = Depends(get_current_user),
    query_service: QueryService = Depends(get_query_service)
) -> query_models.MultipleQueryResponse:
    """
    Executes multiple SQL queries sequentially.
    
    Args:
        request: The multiple SQL queries request payload.
        current_user: The authenticated user instance.
        query_service: The query execution service instance.
        
    Returns:
        query_models.MultipleQueryResponse: The list of results for each executed query.
    """
    if len(request.execution_info) > config.MULTIPLE_QUERY_COUNT:
        raise HTTPException(
            status_code=400,
            detail=f"Too many queries. Maximum: {config.MULTIPLE_QUERY_COUNT}"
        )
    
    results: List[dict[str, Any]] = []
    
    for execution_info in request.execution_info:
        result: dict[str, Any] = await query_service.execute_query(
            query=execution_info.query,
            user=current_user,
            server_name=execution_info.servername,
            database_name=execution_info.database_name,
            ad_hoc_mask_columns=execution_info.ad_hoc_mask_columns
        )
        results.append(result)
    
    return query_models.MultipleQueryResponse(results=results)


@router.get("/database_information", response_model=query_models.DatabaseInformationResponse)
async def get_database_information(
    current_user: User = Depends(get_current_user),
    db_provider: DatabaseProvider = Depends(get_db_provider)
) -> dict[str, Any]:
    """
    Returns the list of databases accessible to the user per server.
    
    Args:
        current_user: The authenticated user instance.
        db_provider: The database provider instance.
        
    Returns:
        dict[str, Any]: A mapping of servers to databases.
    """
    db_info: dict[str, Any] = db_provider.get_db_info_db()
    return {"db_info": db_info}

@router.get("/masking_rules", response_model=List[str])
async def get_masking_rules(
    servername: str,
    database_name: str,
    current_user: User = Depends(get_current_user),
    query_service: QueryService = Depends(get_query_service)
) -> List[str]:
    """
    Returns the list of column names persistently masked by admin for the given server and database.
    """
    rules = await query_service.get_active_masking_rules(servername, database_name)
    return rules
