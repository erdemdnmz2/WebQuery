"""
Workspace Router
Kullanıcı workspace (kaydedilmiş query) yönetimi endpoint'leri
"""
from fastapi import APIRouter, Depends, status, HTTPException, Response, Request
from fastapi.responses import FileResponse
from .schemas import *

from dependencies import get_app_db, get_workspace_service, ensure_owner, get_session_cache, get_db_provider
from authentication.services import get_current_user

from app_database.models import User, Workspace, QueryData
from app_database import AppDatabase

from .services import WorkspaceService
from query_execution import schemas as query_models
from database_provider import DatabaseProvider

router = APIRouter(prefix="/api")

@router.post("/workspaces")
async def create_workspace(
    request: WorkspaceCreate,
    current_user : User = Depends(get_current_user),
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
    current_user : User = Depends(get_current_user),
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
    _ws: Workspace = Depends(ensure_owner),
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
    _ws: Workspace = Depends(ensure_owner),
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
    _ws: Workspace = Depends(ensure_owner),
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
        result = await service.get_workspace_detail_by_id(db, workspace_id, _ws.user_id)
        if not result:
            raise HTTPException(status_code=404, detail="Workspace not found")
        return result


@router.post("/execute_workspace/{workspace_id}", response_model=query_models.SQLResponse)
async def execute_workspace(
    workspace_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    workspace_service: WorkspaceService = Depends(get_workspace_service),
    app_db: AppDatabase = Depends(get_app_db),
    session_cache = Depends(get_session_cache),
    db_provider: DatabaseProvider = Depends(get_db_provider)
):
    """
    Execute the stored query for a workspace server-side.

    Requirements:
    - User must have a valid session.
    - Workspace must exist.
    - Workspace.show_results must be True and queryData.status == 'approved_with_results'.

    Only the workspace_id is accepted from the client to avoid arbitrary SQL execution.
    """
    # Delegate execution to WorkspaceService which enforces approval rules (including session validation)
    result = await workspace_service.execute_workspace(
        workspace_id=workspace_id,
        current_user=current_user,
        session_cache=session_cache,
        db_provider=db_provider
    )

    if result.get("response_type") == "error":
        # map to HTTP errors for common cases
        err = result.get("error", "Execution failed")
        if "not found" in err.lower():
            raise HTTPException(status_code=404, detail=err)
        if "not approved" in err.lower() or "not approved for execution" in err.lower():
            raise HTTPException(status_code=403, detail=err)
        if "session" in err.lower():
            raise HTTPException(status_code=401, detail=err)
        raise HTTPException(status_code=400, detail=err)

    return result


@router.get("/workspaces/{workspace_id}/execute", response_class=FileResponse)
def workspace_execute_page(
    workspace_id: int,
    current_user: User = Depends(get_current_user),
    _ws: Workspace = Depends(ensure_owner)
):
    """
    Serve a lightweight workspace execution page (static HTML).

    Access is limited to the workspace owner by the `ensure_owner` dependency.
    """
    return FileResponse("templates/workspace_execute.html")