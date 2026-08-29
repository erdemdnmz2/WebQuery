"""
Admin Schemas
Pydantic models for admin approval endpoints
"""
from typing import Any, Literal

from pydantic import BaseModel, Field


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

class MaskingRuleSchema(BaseModel):
    """One persisted masking rule.

    `table_name` is now enforced (OQ-2026-013): a rule applies only to the
    tables a query actually reads, so `Customers.email` no longer blanks
    `Suppliers.email`.

    `masking_type` is constrained to the single strategy the engine implements.
    It was previously free text defaulting to `"default"` and was never read at
    all, so the admin screen offered a choice that had no effect. Validating it
    here keeps the stored rule and the applied behaviour the same thing.
    """

    table_name: str = Field(min_length=1, max_length=256)
    column_name: str = Field(min_length=1, max_length=256)
    masking_type: Literal["full"] = "full"
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
    role: str # "READER", "WRITER", "DDL"; DB ADMIN is OWNER-managed.


class DatabaseMemberSchema(BaseModel):
    """A user who currently holds access to a database."""

    user_id: int
    username: str
    email: str
    role: str
    is_admin: bool
    is_active: bool


class DatabaseCandidateSchema(BaseModel):
    """An active user who could be granted access.

    Username and email only: enough to name a colleague, nothing about their
    lifecycle, platform role, or access elsewhere.
    """

    user_id: int
    username: str
    email: str


class DatabaseUsersResponse(BaseModel):
    database_id: int
    #: What the registration provisions, so the UI offers only grantable tiers.
    connection_mode: Literal["ro", "ro_rw", "ro_rw_ddl"] | None = None
    members: list[DatabaseMemberSchema]
    candidates: list[DatabaseCandidateSchema]
