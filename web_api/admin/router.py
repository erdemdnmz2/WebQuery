"""
Admin Router
Admin query approval/rejection endpoints
"""
import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import select

from app_database.app_database import AppDatabase
from app_database.models import AuditLog, User
from common.audit_actions import AuditAction, AuditTarget
from common.roles import mode_from_credentials
from dependencies import (
    admin_required,
    get_admin_service,
    get_app_db,
    platform_admin_required,
)

from .schemas import (
    AdminApprovalsList,
    AdminPreviewResponse,
    AdminUserSummary,
    ApprovalRequest,
    DatabaseAddRequest,
    DatabaseListResponse,
    DatabaseResponseSchema,
    MaskingRuleSchema,
    MaskingRulesSaveRequest,
    RejectRequest,
    UserAssociationRequest,
)
from .services import AdminService

router = APIRouter(prefix="/api/admin")


def _peer_ip(request: Request) -> str | None:
    return request.client.host if request.client else None

@router.get("/queries_to_approve", response_model=AdminApprovalsList)
async def get_queries_to_approve(
    current_admin: User = Depends(admin_required),
    service: AdminService = Depends(get_admin_service)
):
    """
    Returns the list of queries waiting for approval.
    """
    workspaces = await service.get_workspaces_for_approval(current_admin)
    return {"waiting_approvals": workspaces}

@router.post("/approve_query/{workspace_id}")
async def approve_query(
    workspace_id: int,
    approval: ApprovalRequest,
    request: Request,
    current_admin: User = Depends(admin_required),
    service: AdminService = Depends(get_admin_service)
):
    """
    Approves and executes the query.
    """
    # call service approve (sets show_results and query status)
    result = await service.approve(
        workspace_id,
        approval.show_results,
        current_admin,
        client_ip=_peer_ip(request),
    )

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
    rejection: RejectRequest,
    request: Request,
    current_admin: User = Depends(admin_required),
    service: AdminService = Depends(get_admin_service)
):
    """
    Rejects the query.
    """
    result = await service.reject_query_by_workspace_id(
        workspace_id,
        rejection.reason,
        current_admin,
        client_ip=_peer_ip(request),
    )
    
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
    request: Request,
    current_admin : User = Depends(admin_required),
    service : AdminService = Depends(get_admin_service)
):
    """
    Admin için workspace sorgusunu preview eder (önizleme)

    Admin yetkisi gerektirir. execute_for_preview, query'yi çalıştırır ancak status değiştirmez.
    """
    result = await service.execute_for_preview(
        workspace_id, current_admin, client_ip=_peer_ip(request)
    )

    if isinstance(result, dict) and result.get("response_type") == "error":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result.get("error"))
    
    return result

@router.post("/add_database")
async def add_database(
    request: DatabaseAddRequest,
    http_request: Request,
    current_admin: User = Depends(admin_required),
    service: AdminService = Depends(get_admin_service)
):
    """
    Adds a new database to the system.
    """
    result = await service.db_addition_service.add_database(
        servername=request.servername,
        database_name=request.database_name,
        tech_name=request.tech_name,
        connection_mode=request.connection_mode,
        username_ro=request.username_ro,
        password_ro=request.password_ro,
        username_rw=request.username_rw,
        password_rw=request.password_rw,
        username_ddl=request.username_ddl,
        password_ddl=request.password_ddl,
        admin_user=current_admin,
        client_ip=_peer_ip(http_request),
    )
    
    if result.get("success"):
        return {
            "message": result.get("message"),
            "db_uuid": result.get("db_uuid"),
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
    dbs = await service.list_databases(current_admin)
    return {"databases": [
        DatabaseResponseSchema(
            id=db.id,
            servername=db.servername,
            database_name=db.database_name,
            technology=db.technology,
            connection_mode=mode_from_credentials(
                has_ro=bool(db.username_ro and db.password_ro),
                has_rw=bool(db.username_rw and db.password_rw),
                has_ddl=bool(db.username_ddl and db.password_ddl),
            ),
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

@router.get("/databases/{database_id}/masking_rules", response_model=list[MaskingRuleSchema])
async def get_masking_rules(
    database_id: int,
    current_admin: User = Depends(admin_required),
    service: AdminService = Depends(get_admin_service)
):
    """
    Gets all masking rules for a database.
    """
    rules = await service.get_all_masking_rules(database_id, current_admin)
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
    http_request: Request,
    current_admin: User = Depends(admin_required),
    service: AdminService = Depends(get_admin_service)
):
    """
    Saves/updates the masking rules for a database.
    """
    success = await service.save_masking_rules(
        database_id,
        request.rules,
        current_admin,
        client_ip=_peer_ip(http_request),
    )
    if success:
        return {"success": True, "message": "Masking rules saved successfully"}
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to save masking rules"
        )

@router.post("/associate_user")
async def associate_user(
    request: UserAssociationRequest,
    http_request: Request,
    current_admin: User = Depends(admin_required),
    service: AdminService = Depends(get_admin_service)
):
    """
    Associates a user with a database under a specific role (READER, WRITER, ADMIN).
    """
    result = await service.associate_user_to_database(
        user_id=request.user_id,
        database_id=request.database_id,
        role=request.role,
        admin_user=current_admin,
        client_ip=_peer_ip(http_request),
    )
    if result.get("success"):
        return {"success": True, "message": result.get("message")}
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "Failed to associate user")
        )


@router.post("/users/{user_id}/disable")
async def disable_user(
    user_id: int,
    http_request: Request,
    current_admin: User = Depends(admin_required),
    service: AdminService = Depends(get_admin_service),
):
    """Disable a user and revoke all of their active sessions."""
    return await service.disable_user(
        user_id=user_id,
        admin_user=current_admin,
        client_ip=_peer_ip(http_request),
        trace_id=getattr(http_request.state, "request_id", None),
    )


@router.get("/users", response_model=list[AdminUserSummary])
async def list_users(
    _platform_admin: User = Depends(platform_admin_required),
    service: AdminService = Depends(get_admin_service),
):
    """List users for the platform-scoped activation console."""
    users = await service.list_users()
    return [
        AdminUserSummary(
            id=user.id,
            username=user.username,
            email=user.email,
            is_active=bool(user.is_active),
            status=(
                "active"
                if user.is_active
                else "disabled"
                if user.disabled_at is not None
                else "pending"
            ),
            created_at=user.created_at,
        )
        for user in users
    ]


@router.post("/users/{user_id}/enable")
async def enable_user(
    user_id: int,
    http_request: Request,
    platform_admin: User = Depends(platform_admin_required),
    service: AdminService = Depends(get_admin_service),
):
    """Enable a pending or disabled account at platform scope."""
    return await service.enable_user(
        user_id=user_id,
        admin_user=platform_admin,
        client_ip=_peer_ip(http_request),
        trace_id=getattr(http_request.state, "request_id", None),
    )


@router.get("/audit_log")
async def get_audit_log(
    action: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 200,
    _admin_user: User = Depends(admin_required),
    app_db: AppDatabase = Depends(get_app_db),
):
    """Return validated, filtered audit records from newest to oldest."""
    action_filter: AuditAction | None = None
    if action is not None:
        try:
            action_filter = AuditAction(action)
        except ValueError as exc:
            valid_actions = ", ".join(sorted(item.value for item in AuditAction))
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown audit action: '{action}'. Valid actions: {valid_actions}",
            ) from exc

    target_filter: AuditTarget | None = None
    if target_type is not None:
        try:
            target_filter = AuditTarget(target_type)
        except ValueError as exc:
            valid_targets = ", ".join(sorted(item.value for item in AuditTarget))
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Unknown audit target type: '{target_type}'. "
                    f"Valid target types: {valid_targets}"
                ),
            ) from exc

    async with app_db.get_app_db() as db:
        statement = select(AuditLog).order_by(AuditLog.id.desc()).limit(limit)
        if action_filter is not None:
            statement = statement.where(AuditLog.action == action_filter)
        if target_filter is not None:
            statement = statement.where(AuditLog.target_type == target_filter)
        if target_id is not None:
            statement = statement.where(AuditLog.target_id == str(target_id))
        rows = (await db.execute(statement)).scalars().all()

    return [
        {
            "id": row.id,
            "at": row.created_at,
            "actor": row.actor_username,
            "action": row.action,
            "target": f"{row.target_type}:{row.target_id}",
            "details": json.loads(row.details) if row.details else None,
            "ip": row.client_ip,
        }
        for row in rows
    ]
