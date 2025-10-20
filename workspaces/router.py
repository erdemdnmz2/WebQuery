
from fastapi import APIRouter, Depends, status, HTTPException, Response
from schemas import *
from dependencies import get_app_db, get_workspace_service
from authentication.services import get_current_user
from app_database import AppDatabase
from services import WorkspaceService

router = APIRouter(prefix="/api")

# Workspace oluşturma
@router.post("/workspaces")
async def create_workspace(
    request: WorkspaceCreate,
    current_user = Depends(get_current_user),
    service: WorkspaceService = Depends(get_workspace_service),
    app_db: AppDatabase = Depends(get_app_db)
):
    async with app_db.get_app_db() as db:
        result = await service.create_workspace(db=db, workspace_data=request, user_id=current_user.id)
    if result.get("success"):
        return result
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result.get("error", "Workspace could not be created."))

# Workspace listeleme
@router.get("/workspaces", response_model=WorkspaceList)
async def get_workspaces(
    current_user = Depends(get_current_user),
    service: WorkspaceService = Depends(get_workspace_service),
    app_db: AppDatabase = Depends(get_app_db)
):
    async with app_db.get_app_db() as db:
        workspaces = await service.get_workspace_by_id(db, current_user.id)
        return {"workspaces": workspaces}

# Workspace silme
@router.delete("/workspaces/{workspace_id}")
async def delete_workspace(
    workspace_id: int,
    current_user = Depends(get_current_user),
    service: WorkspaceService = Depends(get_workspace_service),
    app_db: AppDatabase = Depends(get_app_db)
):
    async with app_db.get_app_db() as db:
        success = await service.delete_workspace_by_id(workspace_id, db=db)
        if success:
            return Response(status_code=status.HTTP_200_OK)
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Workspace could not be deleted.")

# Workspace güncelleme
@router.put("/workspaces/{workspace_id}")
async def update_workspace(
    workspace_id: int,
    request: WorkspaceUpdate,
    current_user = Depends(get_current_user),
    service: WorkspaceService = Depends(get_workspace_service),
    app_db: AppDatabase = Depends(get_app_db)
):
    async with app_db.get_app_db() as db:
        success = await service.update_workspace(db, workspace_id, query=request.query, status=request.status)
        if success:
            return Response(status_code=status.HTTP_200_OK)
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Workspace could not be updated.")
        

# Workspace detayını id ile getir
@router.get("/get_workspace_by_id/{workspace_id}")
async def get_workspace_by_id(
    workspace_id: int,
    current_user = Depends(get_current_user),
    service: WorkspaceService = Depends(get_workspace_service),
    app_db: AppDatabase = Depends(get_app_db)
):
    async with app_db.get_app_db() as db:
        result = await service.get_workspace_detail_by_id(db, workspace_id, current_user.id)
        if not result:
            raise HTTPException(status_code=404, detail="Workspace not found")
        return result