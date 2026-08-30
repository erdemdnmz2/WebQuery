"""Domain exceptions for platform OWNER operations."""

from common.exceptions import BaseServiceException


class OwnerUserNotFoundError(BaseServiceException):
    status_code = 404
    code = "OWNER_USER_NOT_FOUND"


class OwnerDatabaseNotFoundError(BaseServiceException):
    status_code = 404
    code = "OWNER_DATABASE_NOT_FOUND"


class OwnerDatabaseAlreadyExistsError(BaseServiceException):
    status_code = 400
    code = "DATABASE_ALREADY_EXISTS"


class InactiveDatabaseAdminError(BaseServiceException):
    status_code = 400
    code = "DATABASE_ADMIN_INACTIVE"


class CannotDisableSelfError(BaseServiceException):
    status_code = 400
    code = "CANNOT_DISABLE_SELF"


class LastActiveOwnerError(BaseServiceException):
    status_code = 409
    code = "LAST_ACTIVE_OWNER"


class LastDatabaseAdminError(BaseServiceException):
    status_code = 409
    code = "LAST_DATABASE_ADMIN"


class ConnectionModeConflictError(BaseServiceException):
    """Raised when narrowing a connection mode would strand existing grants.

    Per OQ-2026-018 the request is refused rather than silently demoting users,
    and the conflicting grants travel with the error so an administrator can
    act on them without hunting for the list.
    """

    status_code = 409
    code = "CONNECTION_MODE_CONFLICT"

    def __init__(
        self,
        message: str,
        conflicts: list[dict] | None = None,
        original_exception: Exception | None = None,
    ) -> None:
        super().__init__(message, original_exception)
        self.conflicts = conflicts or []

    def response_context(self) -> dict:
        # Usernames and roles only; no credential material.
        return {"conflicts": self.conflicts}
