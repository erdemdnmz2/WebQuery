"""
Workspace Router
Kullanıcı workspace (kaydedilmiş query) yönetimi endpoint'leri
"""
from fastapi import APIRouter, Depends, status, HTTPException, Response
from .schemas import *
from dependencies import get_app_db, get_workspace_service
from authentication.services import get_current_user
from app_database import AppDatabase
from .services import WorkspaceService

router = APIRouter(prefix="/api")

@router.post("/workspaces")
async def create_workspace(
    request: WorkspaceCreate,
    current_user = Depends(get_current_user),
    service: WorkspaceService = Depends(get_workspace_service),
    app_db: AppDatabase = Depends(get_app_db)
):
    """
    Yeni workspace oluşturur
    
    Args:
        request: Workspace oluşturma verisi (name, query, servername, database)
    
    Returns:
        Dict: {"success": true, "workspace_id": int}
    
    Raises:
        HTTPException 400: Workspace oluşturulamazsa
    """
    async with app_db.get_app_db() as db:
        result = await service.create_workspace(db=db, workspace_data=request, user_id=current_user.id)
    if result.get("success"):
        return result
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result.get("error", "Workspace could not be created."))

@router.get("/workspaces", response_model=WorkspaceList)
async def get_workspaces(
    current_user = Depends(get_current_user),
    service: WorkspaceService = Depends(get_workspace_service),
    app_db: AppDatabase = Depends(get_app_db)
):
    """
    Kullanıcının tüm workspace'lerini listeler
    
    Returns:
        WorkspaceList: Kullanıcıya ait workspace listesi
    """
    async with app_db.get_app_db() as db:
        workspaces = await service.get_workspace_by_id(db, current_user.id)
        return {"workspaces": workspaces}

@router.delete("/workspaces/{workspace_id}")
async def delete_workspace(
    workspace_id: int,
    current_user = Depends(get_current_user),
    service: WorkspaceService = Depends(get_workspace_service),
    app_db: AppDatabase = Depends(get_app_db)
):
    """
    Workspace'i siler
    
    Args:
        workspace_id: Silinecek workspace ID'si
    
    Returns:
        Response: 200 OK
    
    Raises:
        HTTPException 400: Workspace silinemezse
    
    Note:
        İlişkili queryData kaydı da silinir
    """
    async with app_db.get_app_db() as db:
        success = await service.delete_workspace_by_id(workspace_id, db=db)
        if success:
            return Response(status_code=status.HTTP_200_OK)
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Workspace could not be deleted.")

@router.put("/workspaces/{workspace_id}")
async def update_workspace(
    workspace_id: int,
    request: WorkspaceUpdate,
    current_user = Depends(get_current_user),
    service: WorkspaceService = Depends(get_workspace_service),
    app_db: AppDatabase = Depends(get_app_db)
):
    """
    Workspace'i günceller (query ve/veya status)
    
    Args:
        workspace_id: Güncellenecek workspace ID'si
        request: Güncelleme verisi (query, status)
    
    Returns:
        Response: 200 OK
    
    Raises:
        HTTPException 400: Workspace güncellenemezse
    """
    async with app_db.get_app_db() as db:
        success = await service.update_workspace(db, workspace_id, query=request.query, status=request.status)
        if success:
            return Response(status_code=status.HTTP_200_OK)
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Workspace could not be updated.")
        
@router.get("/get_workspace_by_id/{workspace_id}")
async def get_workspace_by_id(
    workspace_id: int,
    current_user = Depends(get_current_user),
    service: WorkspaceService = Depends(get_workspace_service),
    app_db: AppDatabase = Depends(get_app_db)
):
    """
    Workspace detaylarını ID ile getirir
    
    Args:
        workspace_id: Detayı getirilecek workspace ID'si
    
    Returns:
        Dict: Workspace detayları (name, query, servername, database, status)
    
    Raises:
        HTTPException 404: Workspace bulunamazsa veya kullanıcıya ait değilse
    
    Note:
        Sadece workspace sahibi erişebilir
    """
    async with app_db.get_app_db() as db:
        result = await service.get_workspace_detail_by_id(db, workspace_id, current_user.id)
        if not result:
            raise HTTPException(status_code=404, detail="Workspace not found")
        return result