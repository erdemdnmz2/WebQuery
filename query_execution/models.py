"""
Query Execution Schemas
Pydantic models for query execution endpoints
"""
from pydantic import BaseModel
from typing import List, Dict, Any, Optional


class SQLQuery(BaseModel):
    """Single SQL query request"""
    servername: str
    database_name: str
    query: str


class SQLResponse(BaseModel):
    """SQL query response"""
    response_type: str  # "data" or "error"
    data: List[Dict[str, Any]]
    message: Optional[str] = None
    error: Optional[str] = None


class ExecutionInfo(BaseModel):
    """Execution information for multiple queries"""
    servername: str
    database_name: str
    query: str


class MultipleQueryRequest(BaseModel):
    """Multiple query execution request"""
    execution_info: List[ExecutionInfo]


class MultipleQueryResponse(BaseModel):
    """Multiple query execution response"""
    results: List[SQLResponse]


class DatabaseInformationResponse(BaseModel):
    """Database information response"""
    db_info: Dict[str, List[str]]  # {servername: [database_names]}
