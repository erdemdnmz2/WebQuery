"""Server-side bootstrap and startup invariants for platform OWNER accounts."""

import logging

from pydantic import EmailStr, TypeAdapter
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app_database.app_database import AppDatabase
from app_database.models import User
from common.audit import log_in
from common.audit_actions import AuditAction, AuditTarget
from common.audit_details import OwnerBootstrapAuditDetails

logger = logging.getLogger(__name__)
BOOTSTRAP_ACTOR = "system:owner-bootstrap"
_EMAIL_ADAPTER = TypeAdapter(EmailStr)


async def bootstrap_owner(
    app_db: AppDatabase,
    *,
    email: str,
    username: str | None = None,
    password: str | None = None,
) -> tuple[int, bool]:
    """Create or promote one active OWNER from a trusted server-side CLI.

    A missing identity requires both a username and password. Existing users
    are matched by normalized email and never have their password changed.
    """
    normalized_email = str(_EMAIL_ADAPTER.validate_python(email.strip())).casefold()
    normalized_username = username.strip() if username else None
    if username is not None and not normalized_username:
        raise ValueError("Yeni OWNER kullanıcı adı boş olamaz.")
    created = False
    activated = False

    try:
        async with app_db.get_app_db() as db, db.begin():
            user = (
                await db.execute(
                    select(User)
                    .where(func.lower(User.email) == normalized_email)
                    .with_for_update()
                )
            ).scalars().first()

            if user is None:
                if not normalized_username or not password:
                    raise ValueError(
                        "Kullanıcı bulunamadı; yeni OWNER için --username ve parola gerekir."
                    )
                user = User(
                    username=normalized_username,
                    email=normalized_email,
                    is_active=True,
                    is_platform_owner=True,
                )
                user.set_password(password)
                db.add(user)
                await db.flush()
                created = True
                activated = True
            else:
                if user.is_platform_owner and user.is_active:
                    return user.id, False
                activated = not bool(user.is_active)
                user.is_platform_owner = True
                user.is_active = True
                user.disabled_at = None
                user.disabled_by = None

            await log_in(
                db,
                actor_username=BOOTSTRAP_ACTOR,
                action=AuditAction.OWNER_GRANTED,
                target_type=AuditTarget.USER,
                target_id=user.id,
                details=OwnerBootstrapAuditDetails(
                    created_user=created,
                    activated_user=activated,
                ),
            )

            user_id = user.id
    except IntegrityError as exc:
        raise ValueError("OWNER e-posta adresi veya kullanıcı adı zaten kayıtlı.") from exc

    return user_id, True


async def ensure_active_owner(app_db: AppDatabase) -> None:
    """Fail startup closed when no active OWNER exists."""
    async with app_db.get_app_db() as db:
        count = await db.scalar(
            select(func.count(User.id)).where(
                User.is_platform_owner.is_(True),
                User.is_active.is_(True),
            )
        )
    if not count:
        logger.critical(
            "Aktif platform OWNER bulunamadı. Sunucuda `python -m scripts.bootstrap_owner --email <email>` komutuyla OWNER bootstrap edin."
        )
        raise SystemExit(1)
