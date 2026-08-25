"""Approval-domain exceptions translated by the global service handler."""

from common.exceptions import BaseServiceException


class ApprovalConflictError(BaseServiceException):
    """Raised when a decision loses the atomic pending-state transition."""

    status_code = 409
    code = "APPROVAL_CONFLICT"


class ApprovalAuthorizationError(BaseServiceException):
    """Raised when the actor cannot decide for the target database."""

    status_code = 403
    code = "APPROVAL_FORBIDDEN"


class ApprovalValidationError(BaseServiceException):
    """Raised when the requested decision is structurally invalid."""

    status_code = 400
    code = "APPROVAL_VALIDATION_ERROR"


class ApprovalNotFoundError(BaseServiceException):
    """Raised when an approval request or its target database is unavailable."""

    status_code = 404
    code = "APPROVAL_REQUEST_NOT_FOUND"
