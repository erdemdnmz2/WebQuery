"""
Authentication Exceptions
Custom exceptions for user authentication, registration, and session verification.
"""
from common.exceptions import BaseServiceException

class UserAlreadyExistsError(BaseServiceException):
    """Raised when registering a new user with an email that is already taken."""
    status_code = 400
    code = "USER_ALREADY_EXISTS"

class InvalidCredentialsError(BaseServiceException):
    """Raised when user login credentials verification fails."""
    status_code = 401
    code = "INVALID_CREDENTIALS"
