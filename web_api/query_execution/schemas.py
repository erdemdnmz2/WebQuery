"""
Query Execution Schemas
Pydantic models for query execution endpoints
"""
from typing import Any

from pydantic import BaseModel


class SQLQuery(BaseModel):
    """Single SQL query request"""
    db_uuid: str
    query: str
    ad_hoc_mask_columns: list[str] | None = None


class SQLResponse(BaseModel):
    """SQL query response"""
    response_type: str  # "data" or "error"
    data: list[dict[str, Any]]
    message: str | None = None
    error: str | None = None


class ExecutionInfo(BaseModel):
    """Execution information for multiple queries"""
    db_uuid: str
    query: str
    ad_hoc_mask_columns: list[str] | None = None


class MultipleQueryRequest(BaseModel):
    """Multiple query execution request"""
    execution_info: list[ExecutionInfo]


class MultipleQueryResponse(BaseModel):
    """Multiple query execution response"""
    results: list[SQLResponse]


class DatabaseInformationResponse(BaseModel):
    """
    Database information response with server metadata
    
    Format:
        {
            servername: {
                "databases": [database_names],
                "technology": "mssql" | "mysql" | "postgresql"
            }
        }
    """
    db_info: dict[str, dict[str, Any]]
