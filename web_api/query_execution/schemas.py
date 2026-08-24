"""
Query Execution Schemas
Pydantic models for query execution endpoints
"""
from pydantic import BaseModel
from typing import List, Dict, Any, Optional


class SQLQuery(BaseModel):
    """Single SQL query request"""
    db_uuid: str
    query: str
    ad_hoc_mask_columns: Optional[List[str]] = None


class SQLResponse(BaseModel):
    """SQL query response"""
    response_type: str  # "data" or "error"
    data: List[Dict[str, Any]]
    message: Optional[str] = None
    error: Optional[str] = None
    # Columns actually masked in `data`, spelled as they appear in the result
    # rows. Empty when no masking was applied - including when the caller is a
    # database admin and masking is deliberately bypassed. Clients must drive
    # any "masked" affordance from this, never from what they requested.
    masked_columns: List[str] = []


class ExecutionInfo(BaseModel):
    """Execution information for multiple queries"""
    db_uuid: str
    query: str
    ad_hoc_mask_columns: Optional[List[str]] = None


class MultipleQueryRequest(BaseModel):
    """Multiple query execution request"""
    execution_info: List[ExecutionInfo]


class MultipleQueryResponse(BaseModel):
    """Multiple query execution response"""
    results: List[SQLResponse]


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
    db_info: Dict[str, Dict[str, Any]]
