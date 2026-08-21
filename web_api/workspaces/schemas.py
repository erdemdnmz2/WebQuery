"""
Workspace Schemas
Pydantic models for workspace endpoints
"""

from pydantic import BaseModel


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
        db_uuid: Target database unique identifier
        status: Query status (saved_in_workspace, waiting_for_approval, etc.)
    """
    id: int
    name: str
    description: str | None = None
    query: str
    servername: str
    database_name: str
    db_uuid: str
    status: str
    show_results: bool | None = None
    owner_id: int
    is_owner: bool | None = None

class WorkspaceCreate(BaseModel):
    """
    Workspace creation schema
    
    Attributes:
        name: Workspace name
        description: Workspace description (optional)
        query: SQL query to save
        db_uuid: Target database unique identifier
    """
    name: str
    description: str | None = None
    query: str
    db_uuid: str

class WorkspaceList(BaseModel):
    """Workspace list response schema"""
    workspaces: list[WorkspaceInfo]

class WorkspaceUpdate(BaseModel):
    """
    Workspace update schema
    
    Attributes:
        query: SQL query to update
        status: Status to update (optional)
    """
    query: str
    status: str | None = None


class WorkspaceExecutionRequest(BaseModel):
    """Workspace execution request containing ad-hoc columns to mask"""
    ad_hoc_mask_columns: list[str] | None = None