"""
Admin Router
Admin query approval/rejection endpoints
"""
from fastapi import APIRouter, Depends, status, HTTPException, Response
from typing import List
from .schemas import (
    AdminApprovalsList, 
    AdminPreviewResponse, 
    ApprovalRequest, 
    DatabaseAddRequest,
    DatabaseListResponse,
    DatabaseResponseSchema,
    MaskingRuleSchema,
    MaskingRulesSaveRequest
)
from dependencies import get_admin_service, admin_required
from .services import AdminService
from app_database.models import User

router = APIRouter(prefix="/api/admin")

@router.get("/queries_to_approve", response_model=AdminApprovalsList)
async def get_queries_to_approve(
    current_admin: User = Depends(admin_required),
    service: AdminService = Depends(get_admin_service)
):
    """
    Returns the list of queries waiting for approval.
    """
    workspaces = await service.get_workspaces_for_approval()
    return {"waiting_approvals": workspaces}

@router.post("/approve_query/{workspace_id}")
async def approve_query(
    workspace_id: int,
    approval: ApprovalRequest,
    current_admin: User = Depends(admin_required),
    service: AdminService = Depends(get_admin_service)
):
    """
    Approves and executes the query.
    """
    # call service approve (sets show_results and query status)
    result = await service.approve(workspace_id, approval.show_results)

    if result.get("success"):
        return result
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "Failed to approve query")
        )

@router.post("/reject_query/{workspace_id}")
async def reject_query(
    workspace_id: int,
    current_admin: User = Depends(admin_required),
    service: AdminService = Depends(get_admin_service)
):
    """
    Rejects the query.
    """
    result = await service.reject_query_by_workspace_id(workspace_id)
    
    if result.get("success"):
        return Response(status_code=status.HTTP_200_OK)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "Failed to reject query")
        )

@router.post("/execute_for_preview/{workspace_id}", response_model=AdminPreviewResponse)
async def execute_for_preview(
    workspace_id: int,
    current_admin : User = Depends(admin_required),
    service : AdminService = Depends(get_admin_service)
):
    """
    Admin için workspace sorgusunu preview eder (önizleme)

    Admin yetkisi gerektirir. execute_for_preview, query'yi çalıştırır ancak status değiştirmez.
    """
    result = await service.execute_for_preview(workspace_id, current_admin)

    if isinstance(result, dict) and result.get("response_type") == "error":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result.get("error"))
    
    return result

@router.post("/add_database")
async def add_database(
    request: DatabaseAddRequest,
    current_admin: User = Depends(admin_required),
    service: AdminService = Depends(get_admin_service)
):
    """
    Adds a new database to the system.
    """
    result = await service.db_addition_service.add_database(
        servername=request.servername,
        database_name=request.database_name,
        tech_name=request.tech_name
    )
    
    if result.get("success"):
        return {
            "message": result.get("message"),
            "db_username": result.get("db_username"),
            "db_password": result.get("db_password")
        }
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "Failed to add database")
        )

@router.get("/databases", response_model=DatabaseListResponse)
async def list_databases(
    current_admin: User = Depends(admin_required),
    service: AdminService = Depends(get_admin_service)
):
    """
    Lists all registered databases in the system.
    """
    dbs = await service.list_databases()
    return {"databases": [
        DatabaseResponseSchema(
            id=db.id,
            servername=db.servername,
            database_name=db.database_name,
            technology=db.technology,
            db_username=db.db_username
        )
        for db in dbs
    ]}

@router.get("/databases/{database_id}/discover_schema")
async def discover_schema(
    database_id: int,
    current_admin: User = Depends(admin_required),
    service: AdminService = Depends(get_admin_service)
):
    """
    Inspects and returns the schema (tables and columns) of a database.
    """
    schema = await service.discover_schema(database_id, current_admin)
    return schema

@router.get("/databases/{database_id}/masking_rules", response_model=List[MaskingRuleSchema])
async def get_masking_rules(
    database_id: int,
    current_admin: User = Depends(admin_required),
    service: AdminService = Depends(get_admin_service)
):
    """
    Gets all masking rules for a database.
    """
    rules = await service.get_all_masking_rules(database_id)
    return [
        MaskingRuleSchema(
            table_name=r.table_name,
            column_name=r.column_name,
            masking_type=r.masking_type,
            is_active=r.is_active
        )
        for r in rules
    ]

@router.post("/databases/{database_id}/masking_rules")
async def save_masking_rules(
    database_id: int,
    request: MaskingRulesSaveRequest,
    current_admin: User = Depends(admin_required),
    service: AdminService = Depends(get_admin_service)
):
    """
    Saves/updates the masking rules for a database.
    """
    success = await service.save_masking_rules(database_id, request.rules)
    if success:
        return {"success": True, "message": "Masking rules saved successfully"}
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to save masking rules"
        )
