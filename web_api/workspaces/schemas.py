"""
Workspace Schemas
Pydantic models for workspace endpoints
"""

from pydantic import BaseModel, ConfigDict


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

    Only the SQL text is client-supplied. `status` was removed deliberately:
    workspace state transitions belong to the approval decision and to the
    execution flow, and accepting one here let an owner mark their own query
    approved. Any unknown field is rejected rather than ignored, so a client
    still sending `status` fails loudly instead of believing it took effect.

    Attributes:
        query: SQL query to update
    """
    model_config = ConfigDict(extra="forbid")

    query: str


class WorkspaceExecutionRequest(BaseModel):
    """Workspace execution request containing ad-hoc columns to mask"""
    ad_hoc_mask_columns: list[str] | None = None