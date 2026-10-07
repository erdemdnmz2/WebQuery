"""HTTP boundary for platform OWNER governance operations."""

from fastapi import APIRouter, Depends, Request

from app_database.models import User
from common.roles import mode_from_credentials
from dependencies import get_owner_service

from .dependencies import owner_required
from .schemas import (
    DatabaseAdminSummary,
    OwnerDatabaseCreate,
    OwnerDatabaseSummary,
    OwnerDatabaseUpdate,
    OwnerUserSummary,
)
from .services import OwnerService

router = APIRouter(prefix="/api/owner")


def _peer_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _trace_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


@router.get("/users", response_model=list[OwnerUserSummary])
async def list_users(
    _owner: User = Depends(owner_required),
    service: OwnerService = Depends(get_owner_service),
):
    users = await service.list_users()
    return [
        OwnerUserSummary(
            id=user.id,
            username=user.username,
            email=user.email,
            is_active=bool(user.is_active),
            is_platform_owner=bool(user.is_platform_owner),
            status=(
                "active"
                if user.is_active
                else "disabled"
                if user.disabled_at is not None
                else "pending"
            ),
            created_at=user.created_at,
        )
        for user in users
    ]


@router.post("/users/{user_id}/enable")
async def enable_user(
    user_id: int,
    request: Request,
    owner: User = Depends(owner_required),
    service: OwnerService = Depends(get_owner_service),
):
    return await service.enable_user(
        user_id,
        owner,
        client_ip=_peer_ip(request),
        trace_id=_trace_id(request),
    )


@router.post("/users/{user_id}/disable")
async def disable_user(
    user_id: int,
    request: Request,
    owner: User = Depends(owner_required),
    service: OwnerService = Depends(get_owner_service),
):
    return await service.disable_user(
        user_id,
        owner,
        client_ip=_peer_ip(request),
        trace_id=_trace_id(request),
    )


@router.get("/databases", response_model=list[OwnerDatabaseSummary])
async def list_databases(
    _owner: User = Depends(owner_required),
    service: OwnerService = Depends(get_owner_service),
):
    databases = await service.list_databases()
    return [
        OwnerDatabaseSummary(
            id=database.id,
            servername=database.servername,
            database_name=database.database_name,
            technology=database.technology,
            connection_mode=mode_from_credentials(
                has_ro=bool(database.username_ro and database.password_ro),
                has_rw=bool(database.username_rw and database.password_rw),
                has_ddl=bool(database.username_ddl and database.password_ddl),
            ),
            is_active=bool(database.is_active),
        )
        for database in databases
    ]


@router.post("/databases", status_code=201)
async def add_database(
    payload: OwnerDatabaseCreate,
    request: Request,
    owner: User = Depends(owner_required),
    service: OwnerService = Depends(get_owner_service),
):
    return await service.add_database(
        payload,
        owner,
        client_ip=_peer_ip(request),
        trace_id=_trace_id(request),
    )


@router.patch("/databases/{database_id}")
async def update_database(
    database_id: int,
    payload: OwnerDatabaseUpdate,
    request: Request,
    owner: User = Depends(owner_required),
    service: OwnerService = Depends(get_owner_service),
):
    """
    Updates a registration's credentials, connection mode, or identity.

    PATCH semantics: an absent field is left alone (OQ-2026-019). Narrowing the
    connection mode is refused with 409 and the conflicting grants while any
    user holds a role the narrowed registration could not serve (OQ-2026-018).
    Renaming carries the matching saved queries along (OQ-2026-017).
    """
    return await service.update_database(
        database_id,
        payload,
        owner,
        client_ip=_peer_ip(request),
        trace_id=_trace_id(request),
    )


@router.delete("/databases/{database_id}")
async def retire_database(
    database_id: int,
    request: Request,
    owner: User = Depends(owner_required),
    service: OwnerService = Depends(get_owner_service),
):
    """
    Retires a registration.

    Deactivation, not deletion (OQ-2026-016): access grants, masking rules and
    the audit trail are all preserved, and the record simply leaves the runtime
    catalogue so nothing can be queried through it.
    """
    return await service.retire_database(
        database_id,
        owner,
        client_ip=_peer_ip(request),
        trace_id=_trace_id(request),
    )


@router.get("/database-admins", response_model=list[DatabaseAdminSummary])
async def list_database_admins(
    _owner: User = Depends(owner_required),
    service: OwnerService = Depends(get_owner_service),
):
    return await service.list_database_admins()


@router.post("/databases/{database_id}/admins/{user_id}")
async def grant_database_admin(
    database_id: int,
    user_id: int,
    request: Request,
    owner: User = Depends(owner_required),
    service: OwnerService = Depends(get_owner_service),
):
    return await service.grant_database_admin(
        database_id,
        user_id,
        owner,
        client_ip=_peer_ip(request),
        trace_id=_trace_id(request),
    )


@router.delete("/databases/{database_id}/admins/{user_id}")
async def revoke_database_admin(
    database_id: int,
    user_id: int,
    request: Request,
    owner: User = Depends(owner_required),
    service: OwnerService = Depends(get_owner_service),
):
    return await service.revoke_database_admin(
        database_id,
        user_id,
        owner,
        client_ip=_peer_ip(request),
        trace_id=_trace_id(request),
    )
