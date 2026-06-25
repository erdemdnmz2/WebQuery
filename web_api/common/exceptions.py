"""
Common Exceptions Module
Contains the base service exception class for modular exception translation.
"""
from typing import Optional

class BaseServiceException(Exception):
    """
    Base exception class for all business/service layer errors.
    
    Attributes:
        message: Safe error message shown to the client.
        status_code: HTTP status code mapped to this exception.
        code: Enterprise error code string (e.g., WORKSPACE_NOT_FOUND).
        original_exception: Underlying infrastructure exception (e.g., SQLAlchemyError).
    """
    status_code: int = 500
    code: str = "INTERNAL_SERVER_ERROR"

    def __init__(self, message: str, original_exception: Optional[Exception] = None) -> None:
        self.message: str = message
        self.original_exception: Optional[Exception] = original_exception
        super().__init__(self.message)
