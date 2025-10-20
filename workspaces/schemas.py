from pydantic import BaseModel
from typing import Optional, List

class WorkspaceInfo(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    query: str
    servername: str
    database_name: str
    status: str

class WorkspaceCreate(BaseModel):
    name: str
    description: Optional[str] = None
    query: str
    servername: str
    database_name: str

class WorkspaceList(BaseModel):
    workspaces: List[WorkspaceInfo]

class WorkspaceUpdate(BaseModel):
    query: str