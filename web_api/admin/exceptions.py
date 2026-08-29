"""
Admin Exceptions
Custom exceptions for administrative services.
"""
from approval.exceptions import ApprovalAuthorizationError, ApprovalConflictError
from common.exceptions import BaseServiceException


class RoleNotSupportedByDatabaseError(BaseServiceException):
    """Raised when a granted role needs a credential tier the database lacks.

    Granting WRITER on a read-only registration would produce an account that
    fails at execution time instead of at grant time, which reads as a broken
    database rather than an incomplete registration.
    """

    status_code = 400
    code = "ROLE_NOT_SUPPORTED_BY_DATABASE"


class DatabaseAdminOwnerRequiredError(BaseServiceException):
    """Raised when a DB ADMIN assignment is attempted outside OWNER scope."""

    status_code = 400
    code = "DATABASE_ADMIN_OWNER_REQUIRED"


__all__ = [
    "ApprovalAuthorizationError",
    "ApprovalConflictError",
    "DatabaseAdminOwnerRequiredError",
    "RoleNotSupportedByDatabaseError",
]
