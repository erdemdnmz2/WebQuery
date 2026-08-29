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
    # Columns actually masked in `data`, spelled as they appear in the result
    # rows. Empty when no masking was applied - including when the caller is a
    # database admin and masking is deliberately bypassed. Clients must drive
    # any "masked" affordance from this, never from what they requested.
    masked_columns: list[str] = []


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
