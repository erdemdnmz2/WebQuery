"""
Query Execution Router Module
FastAPI router for single and multiple SQL query execution.
All routes are strictly typed and documented.
"""
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.future import select

from app_database.app_database import AppDatabase
from app_database.models import Databases, User, UserDatabaseAssociation
from authentication.services import get_current_user
from common.limiter import limiter
from common.roles import effective_mode
from database_provider import DatabaseProvider
from dependencies import get_app_db, get_db_provider, get_query_service
from query_execution import config
from query_execution import schemas as query_models
from query_execution.services import QueryService

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
    client_ip: str | None = request.client.host if request.client else None
    result: dict[str, Any] = await query_service.execute_query(
        query=query_request.query,
        user=current_user,
        db_uuid=query_request.db_uuid,
        ad_hoc_mask_columns=query_request.ad_hoc_mask_columns,
        client_ip=client_ip,
    )
    return result


@router.post("/multiple_query", response_model=query_models.MultipleQueryResponse)
async def multiple_query(
    request: Request,
    query_request: query_models.MultipleQueryRequest,
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
    if len(query_request.execution_info) > config.MULTIPLE_QUERY_COUNT:
        raise HTTPException(
            status_code=400,
            detail=f"Too many queries. Maximum: {config.MULTIPLE_QUERY_COUNT}"
        )
    
    client_ip: str | None = request.client.host if request.client else None
    results: list[dict[str, Any]] = []
    
    for execution_info in query_request.execution_info:
        result: dict[str, Any] = await query_service.execute_query(
            query=execution_info.query,
            user=current_user,
            db_uuid=execution_info.db_uuid,
            ad_hoc_mask_columns=execution_info.ad_hoc_mask_columns,
            client_ip=client_ip,
        )
        results.append(result)
    
    return query_models.MultipleQueryResponse(results=results)


@router.get("/database_information", response_model=query_models.DatabaseInformationResponse)
async def get_database_information(
    current_user: User = Depends(get_current_user),
    db_provider: DatabaseProvider = Depends(get_db_provider),
    app_db: AppDatabase = Depends(get_app_db)
) -> dict[str, Any]:
    """
    Returns the list of databases accessible to the user per server.
    
    Args:
        current_user: The authenticated user instance.
        db_provider: The database provider instance.
        app_db: The app database manager.
        
    Returns:
        dict[str, Any]: A mapping of servers to databases.
    """
    all_db_info: dict[str, Any] = db_provider.get_db_info_db()

    # Retrieve only databases authorized for the user. The role travels with
    # the association row that is already being read, so resolving the
    # capability below costs no extra query.
    async with app_db.get_app_db() as db:
        assoc_res = await db.execute(
            select(UserDatabaseAssociation.database_id, UserDatabaseAssociation.role)
            .where(UserDatabaseAssociation.user_id == current_user.id)
        )
        role_by_db_id = {database_id: role for database_id, role in assoc_res.all()}

        if not role_by_db_id:
            return {"db_info": {}}
            
        db_res = await db.execute(
            select(Databases).where(Databases.id.in_(role_by_db_id.keys()))
        )
        allowed_databases = db_res.scalars().all()
        role_by_uuid = {str(d.uuid): role_by_db_id[d.id] for d in allowed_databases}

    filtered_info = {}
    for server_name, server_data in all_db_info.items():
        tech = server_data.get("technology", "mssql")
        dbs = server_data.get("databases", [])

        # `capability` is what this user can actually execute here: the
        # registration's mode narrowed by their role. Publishing the raw mode
        # would advertise a write tier that the role check then refuses.
        filtered_dbs = [
            {
                **{key: value for key, value in database.items() if key != "connection_mode"},
                "capability": effective_mode(
                    database.get("connection_mode"), role_by_uuid[str(database.get("uuid"))]
                ),
            }
            for database in dbs
            if str(database.get("uuid")) in role_by_uuid
        ]
        if filtered_dbs:
            filtered_info[server_name] = {
                "databases": filtered_dbs,
                "technology": tech
            }
            
    return {"db_info": filtered_info}

@router.get("/masking_rules", response_model=list[str])
async def get_masking_rules(
    db_uuid: str,
    current_user: User = Depends(get_current_user),
    query_service: QueryService = Depends(get_query_service)
) -> list[str]:
    """
    Returns the list of column names persistently masked by admin for the given database UUID.
    """
    rules = await query_service.get_active_masking_rules(db_uuid)
    return rules
