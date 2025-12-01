"""
Workspace Schemas
Pydantic models for workspace endpoints
"""
from pydantic import BaseModel
from typing import Optional, List

class WorkspaceInfo(BaseModel):
    """
    Workspace bilgisi (response)
    
    Attributes:
        id: Workspace ID
        name: Workspace adı
        description: Workspace açıklaması (opsiyonel)
        query: Kaydedilmiş SQL query
        servername: Hedef SQL Server
        database_name: Hedef veritabanı
        status: Query durumu (saved_in_workspace, waiting_for_approval, etc.)
    """
    id: int
    name: str
    description: Optional[str] = None
    query: str
    servername: str
    database_name: str
    status: str
    show_results: Optional[bool] = None
    owner_id: int
    is_owner: Optional[bool] = None

class WorkspaceCreate(BaseModel):
    """
    Workspace oluşturma şeması
    
    Attributes:
        name: Workspace adı
        description: Workspace açıklaması (opsiyonel)
        query: Kaydedilecek SQL query
        servername: Hedef SQL Server
        database_name: Hedef veritabanı
    """
    name: str
    description: Optional[str] = None
    query: str
    servername: str
    database_name: str

class WorkspaceList(BaseModel):
    """Workspace listesi response şeması"""
    workspaces: List[WorkspaceInfo]

class WorkspaceUpdate(BaseModel):
    """
    Workspace güncelleme şeması
    
    Attributes:
        query: Güncellenecek SQL query
        status: Güncellenecek status (opsiyonel)
    """
    query: str
    status: Optional[str] = None