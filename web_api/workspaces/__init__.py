"""
Workspaces Module
User workspace (saved query) management.
"""
from .exceptions import WorkspaceAccessDeniedError, WorkspaceNotFoundError
from .services import WorkspaceService

__all__ = ["WorkspaceAccessDeniedError", "WorkspaceNotFoundError", "WorkspaceService"]
