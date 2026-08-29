"""Wire contracts for the platform OWNER API."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class OwnerUserSummary(BaseModel):
    id: int
    username: str
    email: str
    is_active: bool
    is_platform_owner: bool
    status: Literal["pending", "active", "disabled"]
    created_at: datetime | None = None


class OwnerDatabaseCreate(BaseModel):
    servername: str = Field(min_length=1, max_length=100)
    database_name: str = Field(min_length=1, max_length=100)
    tech_name: Literal["mssql", "postgresql", "mysql"]
    connection_mode: Literal["ro", "ro_rw", "ro_rw_ddl"]
    initial_admin_user_id: int = Field(gt=0)
    username_ro: str | None = None
    password_ro: str | None = None
    username_rw: str | None = None
    password_rw: str | None = None
    username_ddl: str | None = None
    password_ddl: str | None = None

    @model_validator(mode="after")
    def validate_credentials_for_mode(self) -> "OwnerDatabaseCreate":
        required_by_mode = {
            "ro": ("ro",),
            "ro_rw": ("ro", "rw"),
            "ro_rw_ddl": ("ro", "rw", "ddl"),
        }
        supplied = {
            "ro": (self.username_ro, self.password_ro),
            "rw": (self.username_rw, self.password_rw),
            "ddl": (self.username_ddl, self.password_ddl),
        }
        required = required_by_mode[self.connection_mode]
        for tier in required:
            if not all(value and value.strip() for value in supplied[tier]):
                raise ValueError(f"{tier.upper()} kullanıcı adı ve şifresi zorunludur.")
        for tier, values in supplied.items():
            if tier not in required and any(value and value.strip() for value in values):
                raise ValueError(
                    f"{tier.upper()} bilgileri seçilen bağlantı modunda gönderilemez."
                )
        return self


class OwnerDatabaseUpdate(BaseModel):
    """Partial update of a registration (OQ-2026-019).

    PATCH semantics: a field that is absent is left alone. WebQuery never
    returns a stored password (SPEC-0002 s7), so a full-replacement body would
    force an administrator to obtain every other tier's password from the DBA
    just to rotate one. Removing a tier is expressed by narrowing
    `connection_mode`, so an absent field only ever means "do not touch".
    """

    model_config = ConfigDict(extra="forbid")

    servername: str | None = Field(default=None, min_length=1, max_length=100)
    database_name: str | None = Field(default=None, min_length=1, max_length=100)
    connection_mode: Literal["ro", "ro_rw", "ro_rw_ddl"] | None = None
    username_ro: str | None = None
    password_ro: str | None = None
    username_rw: str | None = None
    password_rw: str | None = None
    username_ddl: str | None = None
    password_ddl: str | None = None

    @model_validator(mode="after")
    def reject_empty_update(self) -> "OwnerDatabaseUpdate":
        if not self.model_fields_set:
            raise ValueError("Güncellenecek en az bir alan gönderilmelidir.")
        return self

    def credential_fields(self) -> dict[str, str | None]:
        """Only the credential fields the caller actually sent."""
        names = (
            "username_ro",
            "password_ro",
            "username_rw",
            "password_rw",
            "username_ddl",
            "password_ddl",
        )
        return {
            name: getattr(self, name)
            for name in names
            if name in self.model_fields_set
        }


class OwnerDatabaseSummary(BaseModel):
    id: int
    servername: str
    database_name: str
    technology: str
    connection_mode: Literal["ro", "ro_rw", "ro_rw_ddl"] | None = None
    is_active: bool = True


class DatabaseAdminSummary(BaseModel):
    database_id: int
    database_name: str
    user_id: int
    username: str
    role: str
