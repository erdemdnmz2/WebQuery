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
    """Raised when a query fails the AST security analysis and is sent for admin approval.

    This code means an approval request now exists and the user has something to
    wait for. It used to be raised for authorization failures too, so the client
    drew "sent for approval" over three unrelated outcomes and left users waiting
    on an approval nobody had been asked for. Authorization now has its own codes
    below.
    """
    status_code = 400
    code = "QUERY_REJECTED_BY_ANALYZER"

class QueryBlockedError(BaseServiceException):
    """Raised when a hard-blocked risk class stops the query for everyone.

    No approval can lift this — WebQuery has no supported path for the statement
    — so it must not be reported as "waiting for an administrator".
    """
    status_code = 400
    code = "QUERY_BLOCKED"

class QueryRoleDeniedError(BaseServiceException):
    """Raised when the caller's role may not execute this class of statement."""
    status_code = 403
    code = "QUERY_ROLE_DENIED"

class DatabaseAccessDeniedError(BaseServiceException):
    """Raised when the caller holds no association with the target database."""
    status_code = 403
    code = "DATABASE_ACCESS_DENIED"

class QuerySyntaxError(BaseServiceException):
    """Raised when the query cannot be parsed at all, so no role decision is possible."""
    status_code = 400
    code = "QUERY_SYNTAX_ERROR"
