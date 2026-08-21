"""
Admin Schemas
Pydantic models for admin approval endpoints
"""
from typing import Any

from pydantic import BaseModel


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
    risk_type: str | None = None
    servername: str | None = None

class AdminApprovalsList(BaseModel):
    """Admin approval list response schema"""
    waiting_approvals: list[AdminApprovals]


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
    data: list[dict[str, Any]]
    columns: list[str] | None = None
    row_count: int | None = None
    message: str | None = None
    error: str | None = None


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


class MaskingRuleSchema(BaseModel):
    table_name: str
    column_name: str
    masking_type: str = "default"
    is_active: bool = True


class MaskingRulesSaveRequest(BaseModel):
    rules: list[MaskingRuleSchema]


class DatabaseResponseSchema(BaseModel):
    id: int
    servername: str
    database_name: str
    technology: str
    db_username: str | None = None


class DatabaseListResponse(BaseModel):
    databases: list[DatabaseResponseSchema]


class UserAssociationRequest(BaseModel):
    user_id: int
    database_id: int
    role: str # "READER", "WRITER", "ADMIN"
