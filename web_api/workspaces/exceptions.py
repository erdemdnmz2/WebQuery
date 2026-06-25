"""
Workspaces Exceptions
Custom exceptions for the workspaces service layer.
"""
from common.exceptions import BaseServiceException

class WorkspaceNotFoundError(BaseServiceException):
    """Raised when a requested workspace is not found."""
    status_code = 404
    code = "WORKSPACE_NOT_FOUND"

class WorkspaceAccessDeniedError(BaseServiceException):
    """Raised when a user attempts to access a workspace they do not own."""
    status_code = 403
    code = "WORKSPACE_ACCESS_DENIED"
