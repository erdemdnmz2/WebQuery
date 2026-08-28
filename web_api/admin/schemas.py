"""
Admin Schemas
Pydantic models for admin approval endpoints
"""
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


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


class RejectRequest(BaseModel):
    """Required explanation for a rejected risky query."""

    reason: str = Field(min_length=3, max_length=500)

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
    connection_mode: Literal["ro", "ro_rw", "ro_rw_ddl"]
    username_ro: str | None = None
    password_ro: str | None = None
    username_rw: str | None = None
    password_rw: str | None = None
    username_ddl: str | None = None
    password_ddl: str | None = None

    @model_validator(mode="after")
    def validate_credentials_for_mode(self) -> "DatabaseAddRequest":
        required_by_mode = {
            "ro": ("ro",),
            "ro_rw": ("ro", "rw"),
            "ro_rw_ddl": ("ro", "rw", "ddl"),
        }
        supplied = {
            "ro": (self.username_ro, self.password_ro),
            "rw": (self.username_rw, self.password_rw),
            "ddl": (self.username_ddl, self.password_ddl),
        }
        required = required_by_mode[self.connection_mode]
        for tier in required:
            if not all(value and value.strip() for value in supplied[tier]):
                raise ValueError(f"{tier.upper()} kullanıcı adı ve şifresi zorunludur.")
        for tier, values in supplied.items():
            if tier not in required and any(value and value.strip() for value in values):
                raise ValueError(f"{tier.upper()} bilgileri seçilen bağlantı modunda gönderilemez.")
        return self


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
    connection_mode: Literal["ro", "ro_rw", "ro_rw_ddl"] | None = None


class DatabaseListResponse(BaseModel):
    databases: list[DatabaseResponseSchema]


class UserAssociationRequest(BaseModel):
    user_id: int
    database_id: int
    role: str # "READER", "WRITER", "ADMIN"


class AdminUserSummary(BaseModel):
    id: int
    username: str
    email: str
    is_active: bool
    status: str
    created_at: datetime | None = None
