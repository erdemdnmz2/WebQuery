"""Platform-scoped OWNER operations and their transactional invariants."""
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app_database.app_database import AppDatabase
from app_database.models import Databases, User, UserDatabaseAssociation, UserSession
from common.audit import log_in
from common.audit_actions import AuditAction, AuditTarget
from common.audit_details import (
    DatabaseAdminAuditDetails,
    DatabaseConfigurationAuditDetails,
    UserLifecycleAuditDetails,
)
from common.roles import ADMIN, format_roles, is_admin, parse
from database_provider import DatabaseProvider

from .exceptions import (
    CannotDisableSelfError,
    InactiveDatabaseAdminError,
    LastActiveOwnerError,
    LastDatabaseAdminError,
    OwnerDatabaseAlreadyExistsError,
    OwnerDatabaseNotFoundError,
    OwnerUserNotFoundError,
)
from .schemas import OwnerDatabaseCreate

logger = logging.getLogger(__name__)


def _db_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class OwnerService:
    """Own platform identities and database-governance roots, never query data."""

    def __init__(self, app_db: AppDatabase, db_provider: DatabaseProvider):
        self.app_db = app_db
        self.db_provider = db_provider

    async def list_users(self) -> list[User]:
        async with self.app_db.get_app_db() as db:
            result = await db.execute(select(User).order_by(User.username.asc()))
            return list(result.scalars().all())

    async def enable_user(
        self,
        user_id: int,
        actor: User,
        client_ip: str | None = None,
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        async with self.app_db.get_app_db() as db, db.begin():
            target = await db.get(User, user_id, with_for_update=True)
            if target is None:
                raise OwnerUserNotFoundError("Kullanıcı bulunamadı.")
            if target.is_active:
                return {"success": True, "message": "Kullanıcı zaten aktif."}

            target.is_active = True
            target.disabled_at = None
            target.disabled_by = None
            await log_in(
                db,
                actor=actor,
                action=AuditAction.USER_ENABLED,
                target_type=AuditTarget.USER,
                target_id=target.id,
                details=UserLifecycleAuditDetails(event="enabled", source="owner"),
                client_ip=client_ip,
                trace_id=trace_id,
            )
        return {"success": True, "message": "Kullanıcı etkinleştirildi."}

    async def disable_user(
        self,
        user_id: int,
        actor: User,
        client_ip: str | None = None,
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        if user_id == actor.id:
            raise CannotDisableSelfError("Kendi OWNER hesabınızı devre dışı bırakamazsınız.")

        async with self.app_db.get_app_db() as db, db.begin():
            target = await db.get(User, user_id, with_for_update=True)
            if target is None:
                raise OwnerUserNotFoundError("Kullanıcı bulunamadı.")
            if not target.is_active:
                return {"success": True, "message": "Kullanıcı zaten devre dışı."}

            if target.is_platform_owner:
                active_owners = list(
                    (
                        await db.execute(
                            select(User)
                            .where(
                                User.is_platform_owner.is_(True),
                                User.is_active.is_(True),
                            )
                            .with_for_update()
                        )
                    ).scalars().all()
                )
                if len(active_owners) <= 1:
                    raise LastActiveOwnerError(
                        "Son aktif OWNER devre dışı bırakılamaz. Önce başka bir OWNER bootstrap edin."
                    )

            target.is_active = False
            target.disabled_at = _db_now()
            target.disabled_by = actor.username
            await db.execute(
                update(UserSession)
                .where(UserSession.user_id == target.id, UserSession.revoked_at.is_(None))
                .values(revoked_at=_db_now(), revoked_reason="user disabled by owner")
            )
            await log_in(
                db,
                actor=actor,
                action=AuditAction.USER_DISABLED,
                target_type=AuditTarget.USER,
                target_id=target.id,
                details=UserLifecycleAuditDetails(event="disabled", source="owner"),
                client_ip=client_ip,
                trace_id=trace_id,
            )
        return {"success": True, "message": "Kullanıcı devre dışı bırakıldı."}

    async def list_databases(self) -> list[Databases]:
        async with self.app_db.get_app_db() as db:
            result = await db.execute(
                select(Databases).order_by(Databases.servername, Databases.database_name)
            )
            return list(result.scalars().all())

    async def list_database_admins(self) -> list[dict[str, Any]]:
        async with self.app_db.get_app_db() as db:
            rows = (
                await db.execute(
                    select(UserDatabaseAssociation, User, Databases)
                    .join(User, User.id == UserDatabaseAssociation.user_id)
                    .join(Databases, Databases.id == UserDatabaseAssociation.database_id)
                    .order_by(Databases.database_name, User.username)
                )
            ).all()
            return [
                {
                    "database_id": database.id,
                    "database_name": database.database_name,
                    "user_id": user.id,
                    "username": user.username,
                    "role": association.role,
                }
                for association, user, database in rows
                if is_admin(association.role)
            ]

    async def add_database(
        self,
        request: OwnerDatabaseCreate,
        actor: User,
        client_ip: str | None = None,
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        db_uuid = str(uuid.uuid4())
        try:
            async with self.app_db.get_app_db() as db, db.begin():
                existing = (
                    await db.execute(
                        select(Databases).where(
                            Databases.servername == request.servername,
                            Databases.database_name == request.database_name,
                        )
                    )
                ).scalars().first()
                if existing is not None:
                    raise OwnerDatabaseAlreadyExistsError("Veritabanı zaten kayıtlı.")

                initial_admin = await db.get(
                    User, request.initial_admin_user_id, with_for_update=True
                )
                if initial_admin is None:
                    raise OwnerUserNotFoundError("İlk veritabanı yöneticisi bulunamadı.")
                if not initial_admin.is_active:
                    raise InactiveDatabaseAdminError(
                        "Pasif kullanıcı veritabanı yöneticisi yapılamaz."
                    )

                database = Databases(
                    servername=request.servername.strip(),
                    database_name=request.database_name.strip(),
                    technology=request.tech_name,
                    username_ro=request.username_ro,
                    password_ro=request.password_ro,
                    username_rw=request.username_rw,
                    password_rw=request.password_rw,
                    username_ddl=request.username_ddl,
                    password_ddl=request.password_ddl,
                    uuid=db_uuid,
                )
                db.add(database)
                await db.flush()
                db.add(
                    UserDatabaseAssociation(
                        user_id=initial_admin.id,
                        database_id=database.id,
                        role=ADMIN,
                        is_admin=True,
                    )
                )
                await log_in(
                    db,
                    actor=actor,
                    action=AuditAction.ADD_DATABASE,
                    target_type=AuditTarget.DATABASE,
                    target_id=database.id,
                    details=DatabaseConfigurationAuditDetails(
                        operation="add",
                        servername=database.servername,
                        database_name=database.database_name,
                        technology=database.technology,
                    ),
                    client_ip=client_ip,
                    trace_id=trace_id,
                )
                await log_in(
                    db,
                    actor=actor,
                    action=AuditAction.GRANT_DATABASE_ADMIN,
                    target_type=AuditTarget.USER,
                    target_id=initial_admin.id,
                    details=DatabaseAdminAuditDetails(
                        operation="grant_admin",
                        database_id=database.id,
                        previous_role=None,
                        new_role=ADMIN,
                    ),
                    client_ip=client_ip,
                    trace_id=trace_id,
                )
        except IntegrityError as exc:
            raise OwnerDatabaseAlreadyExistsError("Veritabanı zaten kayıtlı.") from exc

        db_info = await self.app_db.get_db_info()
        self.db_provider.set_db_info(db_info)
        logger.info(
            "Hedef veritabanı OWNER tarafından kaydedildi: database_uuid=%s initial_admin_id=%s",
            db_uuid,
            request.initial_admin_user_id,
        )
        return {"success": True, "message": "Veritabanı kaydedildi.", "db_uuid": db_uuid}

    async def grant_database_admin(
        self,
        database_id: int,
        user_id: int,
        actor: User,
        client_ip: str | None = None,
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        async with self.app_db.get_app_db() as db, db.begin():
            database = await db.get(Databases, database_id)
            if database is None:
                raise OwnerDatabaseNotFoundError("Veritabanı bulunamadı.")
            target = await db.get(User, user_id, with_for_update=True)
            if target is None:
                raise OwnerUserNotFoundError("Kullanıcı bulunamadı.")
            if not target.is_active:
                raise InactiveDatabaseAdminError(
                    "Pasif kullanıcı veritabanı yöneticisi yapılamaz."
                )

            association = (
                await db.execute(
                    select(UserDatabaseAssociation)
                    .where(
                        UserDatabaseAssociation.user_id == user_id,
                        UserDatabaseAssociation.database_id == database_id,
                    )
                    .with_for_update()
                )
            ).scalars().first()
            previous_role = association.role if association else None
            roles = parse(previous_role)
            if ADMIN in roles:
                return {"success": True, "message": "Kullanıcı zaten DB ADMIN."}
            roles.add(ADMIN)
            new_role = format_roles(roles)
            if association is None:
                association = UserDatabaseAssociation(
                    user_id=user_id,
                    database_id=database_id,
                    role=new_role,
                    is_admin=True,
                )
                db.add(association)
            else:
                association.role = new_role
                association.is_admin = True

            await log_in(
                db,
                actor=actor,
                action=AuditAction.GRANT_DATABASE_ADMIN,
                target_type=AuditTarget.USER,
                target_id=user_id,
                details=DatabaseAdminAuditDetails(
                    operation="grant_admin",
                    database_id=database_id,
                    previous_role=previous_role,
                    new_role=new_role,
                ),
                client_ip=client_ip,
                trace_id=trace_id,
            )
        return {"success": True, "message": "DB ADMIN yetkisi verildi."}

    async def revoke_database_admin(
        self,
        database_id: int,
        user_id: int,
        actor: User,
        client_ip: str | None = None,
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        async with self.app_db.get_app_db() as db, db.begin():
            database = await db.get(Databases, database_id)
            if database is None:
                raise OwnerDatabaseNotFoundError("Veritabanı bulunamadı.")
            associations = list(
                (
                    await db.execute(
                        select(UserDatabaseAssociation)
                        .where(UserDatabaseAssociation.database_id == database_id)
                        .with_for_update()
                    )
                ).scalars().all()
            )
            target = next((item for item in associations if item.user_id == user_id), None)
            if target is None or not is_admin(target.role):
                return {"success": True, "message": "Kullanıcı DB ADMIN değil."}
            if sum(1 for item in associations if is_admin(item.role)) <= 1:
                raise LastDatabaseAdminError(
                    "Veritabanının son ADMIN yetkisi kaldırılamaz. Önce başka bir ADMIN atayın."
                )

            previous_role = target.role
            roles = parse(previous_role)
            roles.discard(ADMIN)
            new_role = format_roles(roles) if roles else None
            if new_role is None:
                await db.delete(target)
            else:
                target.role = new_role
                target.is_admin = False
            await log_in(
                db,
                actor=actor,
                action=AuditAction.REVOKE_DATABASE_ADMIN,
                target_type=AuditTarget.USER,
                target_id=user_id,
                details=DatabaseAdminAuditDetails(
                    operation="revoke_admin",
                    database_id=database_id,
                    previous_role=previous_role,
                    new_role=new_role,
                ),
                client_ip=client_ip,
                trace_id=trace_id,
            )
        return {"success": True, "message": "DB ADMIN yetkisi kaldırıldı."}
