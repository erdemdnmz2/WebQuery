from fastapi import APIRouter, Depends, status, HTTPException, Response
from schemas import *
from dependencies import get_admin_service
from authentication.services import get_current_user
from services import AdminService

router = APIRouter(prefix="/api/admin")

@router.get("/queries_to_approve", response_model=AdminApprovalsList)
async def get_queries_to_approve(
    current_user = Depends(get_current_user),
    service: AdminService = Depends(get_admin_service)
):
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    
    workspaces = await service.get_workspaces_for_approval()
    return {"waiting_approvals": workspaces}

@router.post("/approve_query/{workspace_id}")
async def approve_query(
    workspace_id: int,
    current_user = Depends(get_current_user),
    service: AdminService = Depends(get_admin_service)
):
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    
    result = await service.approve_query_by_workspace_id(workspace_id)
    
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
    current_user = Depends(get_current_user),
    service: AdminService = Depends(get_admin_service)
):
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    
    result = await service.reject_query_by_workspace_id(workspace_id)
    
    if result.get("success"):
        return Response(status_code=status.HTTP_200_OK)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "Failed to reject query")
        )
