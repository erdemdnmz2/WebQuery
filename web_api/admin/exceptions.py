"""
Admin Exceptions
Custom exceptions for administrative services.
"""
from common.exceptions import BaseServiceException


class DatabaseAlreadyExistsError(BaseServiceException):
    """Raised when trying to register a database server/name combination that already exists."""
    status_code = 400
    code = "DATABASE_ALREADY_EXISTS"


class ApprovalConflictError(BaseServiceException):
    """Raised when an approval decision loses a concurrent state transition."""

    status_code = 409
    code = "APPROVAL_CONFLICT"


class ApprovalAuthorizationError(BaseServiceException):
    """Raised when an actor is not an ADMIN for the target database."""

    status_code = 403
    code = "APPROVAL_FORBIDDEN"
