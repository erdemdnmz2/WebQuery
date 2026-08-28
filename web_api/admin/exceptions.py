"""
Admin Exceptions
Custom exceptions for administrative services.
"""
from approval.exceptions import ApprovalAuthorizationError, ApprovalConflictError
from common.exceptions import BaseServiceException


class DatabaseAlreadyExistsError(BaseServiceException):
    """Raised when trying to register a database server/name combination that already exists."""
    status_code = 400
    code = "DATABASE_ALREADY_EXISTS"


class AdminUserNotFoundError(BaseServiceException):
    """Raised when an admin targets a user that does not exist."""

    status_code = 404
    code = "USER_NOT_FOUND"


class RoleNotSupportedByDatabaseError(BaseServiceException):
    """Raised when a granted role needs a credential tier the database lacks.

    Granting WRITER on a read-only registration would produce an account that
    fails at execution time instead of at grant time, which reads as a broken
    database rather than an incomplete registration.
    """

    status_code = 400
    code = "ROLE_NOT_SUPPORTED_BY_DATABASE"


class CannotDisableSelfError(BaseServiceException):
    """Raised when an admin attempts to disable their own account."""

    status_code = 400
    code = "CANNOT_DISABLE_SELF"


__all__ = [
    "AdminUserNotFoundError",
    "ApprovalAuthorizationError",
    "ApprovalConflictError",
    "CannotDisableSelfError",
    "DatabaseAlreadyExistsError",
    "RoleNotSupportedByDatabaseError",
]
