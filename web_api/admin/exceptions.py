"""
Admin Exceptions
Custom exceptions for administrative services.
"""
from common.exceptions import BaseServiceException

class DatabaseAlreadyExistsError(BaseServiceException):
    """Raised when trying to register a database server/name combination that already exists."""
    status_code = 400
    code = "DATABASE_ALREADY_EXISTS"
