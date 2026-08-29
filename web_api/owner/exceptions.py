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
