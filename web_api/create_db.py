"""One-time bootstrap: create the application database and login if missing.

Idempotent and safe to run on every container start. Table schema is managed
by Alembic (`alembic upgrade head`, run next in entrypoint.sh) — see
docs/adr/ADR-0001-schema-migrations-alembic.md. This only ensures the database
and the login `APP_DATABASE_URL` names exist before that runs.

Readiness waiting lives in `wait_for_db.py` (P1-13): this script used to catch
every exception and log a warning instead of raising, which made it always
"succeed" from entrypoint.sh's point of view even against an unreachable
server, and the alembic step then failed hard immediately after. This script
raises on a real failure, so a caller that runs it knows whether it worked.
"""

import logging
import re

from sqlalchemy import create_engine, make_url, text

from app_database.config import DATABASE_URL
from common.logging_config import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

# SQL Server identifiers accepted here. DDL statements cannot bind an
# identifier as a query parameter, so the database and login names taken from
# APP_DATABASE_URL are validated against this pattern before they are
# interpolated into any statement. A name that fails this check is refused
# rather than passed through, closing the injection path a crafted
# DB_USER/DB_NAME value would otherwise have through this bootstrap step.
_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")


def _validate_identifier(name: str, field: str) -> str:
    if not _SAFE_IDENTIFIER.match(name):
        raise ValueError(
            f"{field} güvenli bir SQL tanımlayıcı değil: {name!r}. "
            "Yalnız harf, rakam ve alt çizgi kabul edilir."
        )
    return name


def _escape_literal(value: str) -> str:
    """Double every single quote for a T-SQL string literal.

    `CREATE LOGIN ... WITH PASSWORD = '...'` takes the password as a literal;
    T-SQL has no parameter placeholder for it. Doubling the quote character is
    the same escaping T-SQL itself applies to a literal containing a quote, so
    a password containing `'` can no longer terminate the literal early and
    inject additional SQL.
    """
    return value.replace("'", "''")


def create_database_and_user_if_not_exists() -> None:
    """
    Checks if the target database exists and creates it if not.
    Also handles custom user creation if DB_USER is not 'sa'.
    Uses a synchronous SQLAlchemy engine with AUTOCOMMIT isolation level.
    """
    logger.info("Uygulama veritabanı ve kullanıcı yapılandırması denetleniyor")

    url = make_url(DATABASE_URL)
    target_db = _validate_identifier(url.database, "Hedef veritabanı adı")
    target_user = url.username
    target_password = url.password
    if target_user and target_user.lower() != "sa":
        _validate_identifier(target_user, "Uygulama kullanıcı adı")

    # We need to connect as 'sa' to create DBs and Users.
    # We assume the password provided in env is the SA password
    # (since docker-compose sets MSSQL_SA_PASSWORD=${DB_PASSWORD})
    sa_url = url.set(
        username='sa',
        password=target_password,
        database='master',
        drivername='mssql+pyodbc'
    )

    # SQL echo may include the CREATE LOGIN password literal. Keep SQL
    # statement logging disabled during bootstrap.
    engine = create_engine(sa_url, echo=False, isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as conn:
            # 1. Create Database if not exists. `target_db` was validated
            #    above; the value itself is still bound as a parameter.
            result = conn.execute(
                text("SELECT 1 FROM sys.databases WHERE name = :name"),
                {"name": target_db},
            )
            if not result.scalar():
                logger.info("Uygulama veritabanı oluşturuluyor")
                conn.execute(text(f"CREATE DATABASE [{target_db}]"))
                logger.info("Uygulama veritabanı oluşturuldu")
            else:
                logger.info("Uygulama veritabanı zaten mevcut")

            # 2. Create User if not 'sa'
            if target_user and target_user.lower() != 'sa':
                logger.info("Uygulama veritabanı kullanıcısı denetleniyor")

                login_check = conn.execute(
                    text("SELECT 1 FROM sys.server_principals WHERE name = :name"),
                    {"name": target_user},
                )
                if not login_check.scalar():
                    logger.info("Uygulama veritabanı giriş hesabı oluşturuluyor")
                    escaped_password = _escape_literal(target_password or "")
                    conn.execute(
                        text(f"CREATE LOGIN [{target_user}] WITH PASSWORD = '{escaped_password}'")
                    )
                    logger.info("Uygulama veritabanı giriş hesabı oluşturuldu")

                # Switch to target database to create User and assign roles
                conn.execute(text(f"USE [{target_db}]"))

                user_check = conn.execute(
                    text("SELECT 1 FROM sys.database_principals WHERE name = :name"),
                    {"name": target_user},
                )
                if not user_check.scalar():
                    logger.info("Uygulama veritabanı kullanıcısı oluşturuluyor")
                    conn.execute(text(f"CREATE USER [{target_user}] FOR LOGIN [{target_user}]"))
                    # db_owner here is scoped to this one application database,
                    # not to the server: the login has no sysadmin membership
                    # and cannot touch any other database. Alembic migrations
                    # run as this same user and need DDL rights (ALTER TABLE,
                    # CREATE INDEX, ...) that a narrower fixed role would not
                    # cover.
                    conn.execute(text(f"ALTER ROLE db_owner ADD MEMBER [{target_user}]"))
                    logger.info("Uygulama veritabanı kullanıcısı ve rolü oluşturuldu")
                else:
                    logger.info("Uygulama veritabanı kullanıcısı zaten mevcut")
    finally:
        engine.dispose()


if __name__ == "__main__":
    create_database_and_user_if_not_exists()
