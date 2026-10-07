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

class WorkspaceNotEditableError(BaseServiceException):
    """Raised when the SQL of a workspace is rewritten in a locked state.

    A query waiting for a decision, or one that already carries an approval,
    cannot have its text changed: the first would let the owner swap the SQL out
    from under the approver, the second would let a single approval cover
    unlimited different statements.
    """
    status_code = 409
    code = "WORKSPACE_NOT_EDITABLE"
