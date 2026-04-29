"""
Workspace Schemas
Pydantic models for workspace endpoints
"""
from pydantic import BaseModel
from typing import Optional, List

class WorkspaceInfo(BaseModel):
    """
    Workspace information (response)
    
    Attributes:
        id: Workspace ID
        name: Workspace name
        description: Workspace description (optional)
        query: Saved SQL query
        servername: Target SQL Server
        database_name: Target database
        status: Query status (saved_in_workspace, waiting_for_approval, etc.)
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
    Workspace creation schema
    
    Attributes:
        name: Workspace name
        description: Workspace description (optional)
        query: SQL query to save
        servername: Target SQL Server
        database_name: Target database
    """
    name: str
    description: Optional[str] = None
    query: str
    servername: str
    database_name: str

class WorkspaceList(BaseModel):
    """Workspace list response schema"""
    workspaces: List[WorkspaceInfo]

class WorkspaceUpdate(BaseModel):
    """
    Workspace update schema
    
    Attributes:
        query: SQL query to update
        status: Status to update (optional)
    """
    query: str
    status: Optional[str] = None