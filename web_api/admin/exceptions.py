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


class DatabaseAdminRequiredError(BaseServiceException):
    """Raised when the caller is not ADMIN on the specific database addressed.

    `admin_required` only establishes ADMIN on *some* database; every scoped
    operation re-checks the one it was given. This carries 403 rather than the
    base 500 so the client can tell an authorization refusal from a fault.
    """

    status_code = 403
    code = "DATABASE_ADMIN_REQUIRED"


class DatabaseNotFoundError(BaseServiceException):
    """Raised when the addressed database registration does not exist."""

    status_code = 404
    code = "DATABASE_NOT_FOUND"


class DatabaseAccessNotFoundError(BaseServiceException):
    """Raised when revoking access a user does not hold."""

    status_code = 404
    code = "DATABASE_ACCESS_NOT_FOUND"


__all__ = [
    "ApprovalAuthorizationError",
    "ApprovalConflictError",
    "DatabaseAccessNotFoundError",
    "DatabaseAdminOwnerRequiredError",
    "DatabaseAdminRequiredError",
    "DatabaseNotFoundError",
    "RoleNotSupportedByDatabaseError",
]
