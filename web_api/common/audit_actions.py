"""Persisted audit action and target vocabulary."""
from enum import StrEnum


class AuditAction(StrEnum):
    GRANT_DATABASE_ACCESS = "grant_database_access"
    REVOKE_DATABASE_ACCESS = "revoke_database_access"
    CHANGE_DATABASE_ROLE = "change_database_role"

    USER_CREATED = "user_created"
    USER_REGISTERED = "user_registered"
    USER_DISABLED = "user_disabled"
    USER_ENABLED = "user_enabled"
    PASSWORD_CHANGED = "password_changed"

    APPROVE_QUERY = "approve_query"
    REJECT_QUERY = "reject_query"
    PREVIEW_QUERY = "preview_query"

    ADD_DATABASE = "add_database"
    REMOVE_DATABASE = "remove_database"
    UPDATE_MASKING_RULES = "update_masking_rules"

    LOGIN = "login"
    LOGIN_FAILED = "login_failed"
    LOGOUT = "logout"
    SESSION_REVOKED = "session_revoked"


class AuditTarget(StrEnum):
    USER = "user"
    DATABASE = "database"
    WORKSPACE = "workspace"
    QUERY = "query"
    SESSION = "session"
    MASKING = "masking_rule"


STATE_CHANGING: frozenset[AuditAction] = frozenset(
    {
        AuditAction.GRANT_DATABASE_ACCESS,
        AuditAction.REVOKE_DATABASE_ACCESS,
        AuditAction.CHANGE_DATABASE_ROLE,
        AuditAction.USER_CREATED,
        AuditAction.USER_REGISTERED,
        AuditAction.USER_DISABLED,
        AuditAction.USER_ENABLED,
        AuditAction.PASSWORD_CHANGED,
        AuditAction.APPROVE_QUERY,
        AuditAction.REJECT_QUERY,
        AuditAction.ADD_DATABASE,
        AuditAction.REMOVE_DATABASE,
        AuditAction.UPDATE_MASKING_RULES,
        AuditAction.SESSION_REVOKED,
    }
)
