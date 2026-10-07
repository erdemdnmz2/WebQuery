"""
Common Exceptions Module
Contains the base service exception class for modular exception translation.
"""


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

    def __init__(self, message: str, original_exception: Exception | None = None) -> None:
        self.message: str = message
        self.original_exception: Exception | None = original_exception
        super().__init__(self.message)

    def response_context(self) -> dict | None:
        """Structured, non-sensitive data the client needs to act on the error.

        Most errors need only a message. A few carry a list the caller must
        resolve before retrying — the grants blocking a connection-mode change,
        for example — and re-deriving that list from prose is not something a
        client should have to do. Subclasses that override this are responsible
        for keeping secrets out of it; it goes straight into the response body.
        """
        return None
