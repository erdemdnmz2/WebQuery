"""Platform-scoped OWNER operations and their transactional invariants."""
import logging
import uuid
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app_database.app_database import AppDatabase
from app_database.models import (
    Databases,
    QueryData,
    User,
    UserDatabaseAssociation,
    UserSession,
)
from common.audit import log_in
from common.audit_actions import AuditAction, AuditTarget
from common.audit_details import (
    DatabaseAdminAuditDetails,
    DatabaseConfigurationAuditDetails,
    UserLifecycleAuditDetails,
)
from common.clock import db_now as _db_now
from common.roles import (
    ADMIN,
    exceeds_mode,
    format_roles,
    is_admin,
    mode_from_credentials,
    parse,
)
from database_provider import DatabaseProvider

from .exceptions import (
    CannotDisableSelfError,
    ConnectionModeConflictError,
    InactiveDatabaseAdminError,
    LastActiveOwnerError,
    LastDatabaseAdminError,
    OwnerDatabaseAlreadyExistsError,
    OwnerDatabaseNotFoundError,
    OwnerUserNotFoundError,
)
from .schemas import OwnerDatabaseCreate, OwnerDatabaseUpdate

logger = logging.getLogger(__name__)


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

    async def list_databases(self, include_retired: bool = False) -> list[Databases]:
        """Registrations, active first.

        The OWNER screen can ask for retired rows too: retirement is reversible
        (re-registering the same server and database revives the row), so
        hiding them entirely would make a retired record unrecoverable from the
        interface.
        """
        async with self.app_db.get_app_db() as db:
            statement = select(Databases).order_by(
                Databases.is_active.desc(),
                Databases.servername,
                Databases.database_name,
            )
            if not include_retired:
                statement = statement.where(Databases.is_active.is_(True))
            result = await db.execute(statement)
            return list(result.scalars().all())

    async def list_database_admins(self) -> list[dict[str, Any]]:
        async with self.app_db.get_app_db() as db:
            rows = (
                await db.execute(
                    select(UserDatabaseAssociation, User, Databases)
                    .join(User, User.id == UserDatabaseAssociation.user_id)
                    .join(Databases, Databases.id == UserDatabaseAssociation.database_id)
                    .where(
                        Databases.is_active.is_(True),
                        # Coarse prefilter only: `role` is a comma-separated
                        # string, so SQL cannot decide membership on its own and
                        # this would also match a hypothetical "ADMINISTRATOR".
                        # It keeps every READER/WRITER row on the server instead
                        # of loading the whole association table to discard it,
                        # and `is_admin` below still makes the real decision.
                        # `ilike` because `parse()` upper-cases on read, so a
                        # legacy row may hold "admin"; case-sensitive `LIKE` on
                        # PostgreSQL would drop it.
                        UserDatabaseAssociation.role.ilike("%ADMIN%"),
                    )
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
                        select(Databases)
                        .where(
                            Databases.servername == request.servername,
                            Databases.database_name == request.database_name,
                        )
                        .with_for_update()
                    )
                ).scalars().first()
                if existing is not None and existing.is_active:
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

                if existing is not None:
                    # A retired registration for this server and database still
                    # holds its uuid, its access grants, its masking rules and
                    # every audit row that points at it, and
                    # (servername, database_name) is unique. Re-registering
                    # therefore revives this row with fresh credentials rather
                    # than inserting a rival one the constraint would reject.
                    database = existing
                    database.is_active = True
                    database.retired_at = None
                    database.retired_by = None
                    database.technology = request.tech_name
                    db_uuid = str(database.uuid)
                else:
                    database = Databases(
                        servername=request.servername.strip(),
                        database_name=request.database_name.strip(),
                        technology=request.tech_name,
                        uuid=db_uuid,
                    )
                    db.add(database)

                database.username_ro = request.username_ro
                database.password_ro = request.password_ro
                database.username_rw = request.username_rw
                database.password_rw = request.password_rw
                database.username_ddl = request.username_ddl
                database.password_ddl = request.password_ddl
                await db.flush()

                admin_association = (
                    await db.execute(
                        select(UserDatabaseAssociation)
                        .where(
                            UserDatabaseAssociation.user_id == initial_admin.id,
                            UserDatabaseAssociation.database_id == database.id,
                        )
                        .with_for_update()
                    )
                ).scalars().first()
                if admin_association is None:
                    db.add(
                        UserDatabaseAssociation(
                            user_id=initial_admin.id,
                            database_id=database.id,
                            role=ADMIN,
                            is_admin=True,
                        )
                    )
                else:
                    roles = parse(admin_association.role)
                    roles.add(ADMIN)
                    admin_association.role = format_roles(roles)
                    admin_association.is_admin = True
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

    async def update_database(
        self,
        database_id: int,
        request: OwnerDatabaseUpdate,
        actor: User,
        client_ip: str | None = None,
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        """Rotate credentials, widen or narrow the mode, or correct the identity.

        Registration used to be add-and-read only, so a DBA rotating `app_rw`
        on the target server had no way to tell WebQuery — and the record could
        not be deleted and re-added either, because (servername, database_name)
        is unique. The only remedy was editing the metadata database by hand.

        Three decisions shape this method:

        * `PATCH` semantics (OQ-2026-019): an absent field is untouched.
        * Identity may change (OQ-2026-017), and the matching `QueryData` rows
          move with it in the same transaction, so saved workspaces stay bound.
        * Narrowing the mode is refused while anyone holds a role the narrowed
          registration could not serve (OQ-2026-018), rather than silently
          downgrading them.
        """
        changed_tiers: list[str] = []
        async with self.app_db.get_app_db() as db, db.begin():
            database = await db.get(Databases, database_id, with_for_update=True)
            if database is None or not database.is_active:
                raise OwnerDatabaseNotFoundError("Veritabanı bulunamadı.")

            previous_mode = mode_from_credentials(
                has_ro=bool(database.username_ro and database.password_ro),
                has_rw=bool(database.username_rw and database.password_rw),
                has_ddl=bool(database.username_ddl and database.password_ddl),
            )
            previous_servername = database.servername
            previous_database_name = database.database_name

            # 1. Credentials. Only the fields actually sent are written.
            for field, value in request.credential_fields().items():
                if getattr(database, field) != value:
                    tier = field.rsplit("_", 1)[-1]
                    if tier not in changed_tiers:
                        changed_tiers.append(tier)
                setattr(database, field, value)

            # 2. Connection mode. Narrowing clears the tiers it drops, which is
            #    the only way to remove a tier under PATCH semantics.
            if request.connection_mode is not None:
                keep = {
                    "ro": {"ro"},
                    "ro_rw": {"ro", "rw"},
                    "ro_rw_ddl": {"ro", "rw", "ddl"},
                }[request.connection_mode]
                conflicts = await self._roles_exceeding_mode(
                    db, database_id, request.connection_mode
                )
                if conflicts:
                    raise ConnectionModeConflictError(
                        "Bu bağlantı modu, mevcut kullanıcı yetkileriyle çelişiyor. "
                        "Önce çakışan yetkileri düşürün.",
                        conflicts=conflicts,
                    )
                for tier in ("ro", "rw", "ddl"):
                    if tier not in keep and (
                        getattr(database, f"username_{tier}")
                        or getattr(database, f"password_{tier}")
                    ):
                        setattr(database, f"username_{tier}", None)
                        setattr(database, f"password_{tier}", None)
                        if tier not in changed_tiers:
                            changed_tiers.append(tier)

            # 3. Identity. Saved queries reference the target by name, not by
            #    key, so they move in this same transaction or not at all.
            next_servername = (
                request.servername.strip()
                if request.servername is not None
                else previous_servername
            )
            next_database_name = (
                request.database_name.strip()
                if request.database_name is not None
                else previous_database_name
            )
            identity_changed = (
                next_servername != previous_servername
                or next_database_name != previous_database_name
            )

            if identity_changed:
                # Checked before the assignment: writing the new name first
                # would let autoflush hit the unique constraint and surface a
                # driver IntegrityError instead of this endpoint's own answer.
                clash = (
                    await db.execute(
                        select(Databases).where(
                            Databases.servername == next_servername,
                            Databases.database_name == next_database_name,
                            Databases.id != database_id,
                        )
                    )
                ).scalars().first()
                if clash is not None:
                    raise OwnerDatabaseAlreadyExistsError(
                        "Bu sunucu ve veritabanı adıyla başka bir kayıt var."
                    )
                database.servername = next_servername
                database.database_name = next_database_name
                await db.execute(
                    update(QueryData)
                    .where(
                        QueryData.servername == previous_servername,
                        QueryData.database_name == previous_database_name,
                    )
                    .values(
                        servername=database.servername,
                        database_name=database.database_name,
                    )
                )

            resulting_mode = mode_from_credentials(
                has_ro=bool(database.username_ro and database.password_ro),
                has_rw=bool(database.username_rw and database.password_rw),
                has_ddl=bool(database.username_ddl and database.password_ddl),
            )
            await log_in(
                db,
                actor=actor,
                action=AuditAction.UPDATE_DATABASE,
                target_type=AuditTarget.DATABASE,
                target_id=database.id,
                # Which tiers changed, never what they changed to (SPEC-0002 s7).
                details=DatabaseConfigurationAuditDetails(
                    operation="update",
                    servername=database.servername,
                    database_name=database.database_name,
                    technology=database.technology,
                    updated_tiers=[
                        tier for tier in ("ro", "rw", "ddl") if tier in changed_tiers
                    ],
                    previous_connection_mode=previous_mode,
                    new_connection_mode=resulting_mode,
                ),
                client_ip=client_ip,
                trace_id=trace_id,
            )
            db_uuid = str(database.uuid)

        # Pools opened with the old credentials must not be reused. Without
        # this the rotation is silently ineffective: the cached engine keeps
        # authenticating with the superseded password until its TTL expires.
        await self.db_provider.close_database_engines(db_uuid)
        self.db_provider.set_db_info(await self.app_db.get_db_info())
        logger.info(
            "Hedef veritabanı kaydı güncellendi: database_uuid=%s degisen_kademeler=%s",
            db_uuid,
            ",".join(changed_tiers) or "-",
        )
        return {
            "success": True,
            "message": "Veritabanı kaydı güncellendi.",
            "updated_tiers": changed_tiers,
            "connection_mode": resulting_mode,
        }

    async def _roles_exceeding_mode(
        self, db, database_id: int, connection_mode: str
    ) -> list[dict[str, Any]]:
        """Users whose granted role the narrowed registration could not serve."""
        rows = (
            await db.execute(
                select(UserDatabaseAssociation, User)
                .join(User, User.id == UserDatabaseAssociation.user_id)
                .where(UserDatabaseAssociation.database_id == database_id)
            )
        ).all()
        conflicts = []
        for association, user in rows:
            unsupported = exceeds_mode(connection_mode, association.role)
            if unsupported:
                conflicts.append(
                    {
                        "user_id": user.id,
                        "username": user.username,
                        "role": association.role,
                        "unsupported_tier": unsupported,
                    }
                )
        return conflicts

    async def retire_database(
        self,
        database_id: int,
        actor: User,
        client_ip: str | None = None,
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        """Deactivate a registration without deleting anything (OQ-2026-016).

        Nothing is removed: access grants, masking rules and the audit trail
        stay exactly as they were. The record simply leaves the runtime
        catalogue, so no query can be routed through it. Registering the same
        server and database again reactivates this row rather than creating a
        second one.
        """
        async with self.app_db.get_app_db() as db, db.begin():
            database = await db.get(Databases, database_id, with_for_update=True)
            if database is None:
                raise OwnerDatabaseNotFoundError("Veritabanı bulunamadı.")
            if not database.is_active:
                return {"success": True, "message": "Veritabanı zaten pasif."}

            database.is_active = False
            database.retired_at = _db_now()
            database.retired_by = actor.username
            await log_in(
                db,
                actor=actor,
                action=AuditAction.REMOVE_DATABASE,
                target_type=AuditTarget.DATABASE,
                target_id=database.id,
                details=DatabaseConfigurationAuditDetails(
                    operation="remove",
                    servername=database.servername,
                    database_name=database.database_name,
                    technology=database.technology,
                ),
                client_ip=client_ip,
                trace_id=trace_id,
            )
            db_uuid = str(database.uuid)

        await self.db_provider.close_database_engines(db_uuid)
        self.db_provider.set_db_info(await self.app_db.get_db_info())
        logger.info("Hedef veritabanı kaydı pasifleştirildi: database_uuid=%s", db_uuid)
        return {"success": True, "message": "Veritabanı kaydı pasifleştirildi."}

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
