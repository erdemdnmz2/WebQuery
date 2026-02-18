"""
Admin Schemas
Pydantic models for admin approval endpoints
"""
from pydantic import BaseModel
from typing import Optional, List
from typing import Dict, Any

class AdminApprovals(BaseModel):
    """
    Query information waiting for admin approval
    
    Attributes:
        user_id: ID of the user sending the query
        workspace_id: Related workspace ID
        username: Username
        query: SQL query waiting for approval
        database: Target database
        status: Query status ("waiting_for_approval", etc.)
        risk_type: Risk type (optional, from analyzer)
        servername: Target SQL Server (optional)
    """
    user_id: int
    workspace_id: int
    username: str
    query: str
    database: str
    status: str
    risk_type: Optional[str] = None
    servername: Optional[str] = None

class AdminApprovalsList(BaseModel):
    """Admin approval list response schema"""
    waiting_approvals: List[AdminApprovals]


class AdminPreviewResponse(BaseModel):
    """
    Preview result by admin

    Attributes:
        response_type: "data" or "error"
        data: List of rows (each row is a dict)
        columns: Optional, list of column names
        row_count: Returned row count
        message: Optional message (e.g. "truncated to MAX_ROW_COUNT")
        error: Error message (if any)
    """
    response_type: str  # "data" or "error"
    data: List[Dict[str, Any]]
    columns: Optional[List[str]] = None
    row_count: Optional[int] = None
    message: Optional[str] = None
    error: Optional[str] = None


class ApprovalRequest(BaseModel):
    """
    Admin approval request schema.

    Attributes:
        show_results: bool - if true, workspace becomes executable
    """
    show_results: bool

class DatabaseAddRequest(BaseModel):
    """
    Schema for adding a new database.
    
    Attributes:
        servername: Server instance name
        database_name: Database name
        tech_name: Technology name (e.g., mssql)
    """
    servername: str
    database_name: str
    tech_name: str
