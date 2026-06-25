"""
Query Execution Exceptions
Custom exceptions for the query execution and security analysis service layer.
"""
from common.exceptions import BaseServiceException

class QueryExecutionError(BaseServiceException):
    """Raised when a SQL query execution fails inside the target database."""
    status_code = 400
    code = "QUERY_EXECUTION_FAILED"

class QueryAnalysisRejectedError(BaseServiceException):
    """Raised when a query fails the AST security analysis and is sent for admin approval."""
    status_code = 400
    code = "QUERY_REJECTED_BY_ANALYZER"
