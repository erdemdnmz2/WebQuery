"""Validated, delta-based details payloads for audit actions."""
from collections.abc import Iterable
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class MaskingRuleAuditItem(BaseModel):
    """The complete state of one masking rule identified by table and column."""

    model_config = ConfigDict(extra="forbid")

    table_name: str
    column_name: str
    masking_type: str
    is_active: bool


class MaskingRulesAuditDetails(BaseModel):
    """The delta of one full masking-rule replacement operation.

    A changed rule is represented as one removal and one addition. This keeps
    each audit event compact without losing the security-relevant old value.
    """

    model_config = ConfigDict(extra="forbid")

    operation: Literal["replace_all"] = "replace_all"
    added_rules: list[MaskingRuleAuditItem] = Field(default_factory=list)
    removed_rules: list[MaskingRuleAuditItem] = Field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return bool(self.added_rules or self.removed_rules)

    @staticmethod
    def _key(rule: Any) -> tuple[str, str]:
        return (str(rule.table_name).casefold(), str(rule.column_name).casefold())

    @staticmethod
    def _to_item(rule: Any) -> MaskingRuleAuditItem:
        return MaskingRuleAuditItem(
            table_name=str(rule.table_name),
            column_name=str(rule.column_name),
            masking_type=str(rule.masking_type),
            is_active=bool(rule.is_active),
        )

    @classmethod
    def _index_rules(
        cls, rules: Iterable[Any]
    ) -> dict[tuple[str, str], MaskingRuleAuditItem]:
        indexed: dict[tuple[str, str], MaskingRuleAuditItem] = {}
        for rule in rules:
            key = cls._key(rule)
            if key in indexed:
                raise ValueError(
                    "Duplicate masking rule for "
                    f"{rule.table_name}.{rule.column_name}"
                )
            indexed[key] = cls._to_item(rule)
        return indexed

    @classmethod
    def from_rule_sets(
        cls, previous_rules: Iterable[Any], requested_rules: Iterable[Any]
    ) -> "MaskingRulesAuditDetails":
        previous = cls._index_rules(previous_rules)
        requested = cls._index_rules(requested_rules)

        removed_keys = previous.keys() - requested.keys()
        added_keys = requested.keys() - previous.keys()
        changed_keys = {
            key
            for key in previous.keys() & requested.keys()
            if previous[key] != requested[key]
        }

        return cls(
            added_rules=[requested[key] for key in sorted(added_keys | changed_keys)],
            removed_rules=[previous[key] for key in sorted(removed_keys | changed_keys)],
        )


class DatabaseAccessAuditDetails(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operation: Literal["grant", "change_role", "revoke"]
    database_id: int | None
    previous_role: str | None = None
    # None on a revoke that removed the association outright.
    new_role: str | None = None


class DatabaseAdminAuditDetails(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operation: Literal["grant_admin", "revoke_admin"]
    database_id: int
    previous_role: str | None = None
    new_role: str | None = None


class OwnerBootstrapAuditDetails(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: Literal["server_cli"] = "server_cli"
    created_user: bool
    activated_user: bool


class DatabaseConfigurationAuditDetails(BaseModel):
    """Server, database and technology only.

    Credential values never enter an audit record (SPEC-0002 s7); an update
    records *which* tiers changed, never what they changed to.
    """

    model_config = ConfigDict(extra="forbid")
    operation: Literal["add", "update", "remove"]
    servername: str
    database_name: str
    technology: str
    #: Credential tiers whose username or password was rewritten by an update.
    updated_tiers: list[Literal["ro", "rw", "ddl"]] = Field(default_factory=list)
    previous_connection_mode: str | None = None
    new_connection_mode: str | None = None


class PasswordChangeAuditDetails(BaseModel):
    """Never carries the old or new password, a hash, or a reset token."""

    model_config = ConfigDict(extra="forbid")
    event: Literal["password_changed"] = "password_changed"
    source: Literal["self_service"] = "self_service"
    #: Other sessions ended by the change; the current one is kept.
    revoked_sessions: int = 0


class QueryDecisionAuditDetails(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["approve", "reject"]
    source: Literal["web", "slack"]
    query_id: int
    database_id: int
    status: str
    show_results: bool | None = None
    reason: str | None = None


class QueryPreviewAuditDetails(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query_id: int
    database_id: int
    row_count: int
    truncated: bool


class UserLifecycleAuditDetails(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event: Literal["registered", "disabled", "enabled"]
    source: Literal["web", "admin", "owner"]


class SessionAuditDetails(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event: Literal["login", "login_failed", "logout", "revoked"]
    reason: str | None = None
