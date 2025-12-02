"""
Admin Router
Admin query onay/red işlemleri endpoint'leri
"""
from fastapi import APIRouter, Depends, status, HTTPException, Response
from .schemas import *
from dependencies import get_admin_service, admin_required
from .schemas import ApprovalRequest
from .services import AdminService
from app_database.models import User

router = APIRouter(prefix="/api/admin")

@router.get("/queries_to_approve", response_model=AdminApprovalsList)
async def get_queries_to_approve(
    current_admin: User = Depends(admin_required),
    service: AdminService = Depends(get_admin_service)
):
    """
    Onay bekleyen query'lerin listesini döndürür
    
    Admin yetkisi gerektirir.
    
    Returns:
        AdminApprovalsList: Onay bekleyen query'ler ve detayları
    
    Raises:
        HTTPException 403: Admin yetkisi yoksa
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
    Query'yi onaylar ve çalıştırır
    
    Admin yetkisi gerektirir.
    
    Args:
        workspace_id: Onaylanacak workspace ID'si
    
    Returns:
        Dict: Query sonuçları ve metadata
    
    Raises:
        HTTPException 403: Admin yetkisi yoksa
        HTTPException 400: Onaylama/çalıştırma başarısızsa
    
    Note:
        Query çalıştırılır ve sonuç döndürülür
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
    Query'yi reddeder
    
    Admin yetkisi gerektirir.
    
    Args:
        workspace_id: Reddedilecek workspace ID'si
    
    Returns:
        Response: 200 OK (başarılı)
    
    Raises:
        HTTPException 403: Admin yetkisi yoksa
        HTTPException 400: Reddetme başarısızsa
    
    Note:
        Query çalıştırılmaz, sadece status güncellenir
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
