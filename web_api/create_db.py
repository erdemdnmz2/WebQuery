
import logging

from sqlalchemy import create_engine, make_url, text

from app_database.config import DATABASE_URL
from common.logging_config import setup_logging

setup_logging()
logger = logging.getLogger(__name__)


def create_database_and_user_if_not_exists():
    """
    Checks if the target database exists and creates it if not.
    Also handles custom user creation if DB_USER is not 'sa'.
    Uses a synchronous SQLAlchemy engine with AUTOCOMMIT isolation level.
    """
    logger.info("Uygulama veritabanı ve kullanıcı yapılandırması denetleniyor")
    try:
        # Parse the configured URL (which might use a custom user)
        url = make_url(DATABASE_URL)
        target_db = url.database
        target_user = url.username
        target_password = url.password

        # We need to connect as 'sa' to create DBs and Users.
        # We assume the password provided in env is the SA password 
        # (since docker-compose sets MSSQL_SA_PASSWORD=${DB_PASSWORD})
        sa_url = url.set(
            username='sa', 
            password=target_password, 
            database='master', 
            drivername='mssql+pyodbc'
        )
        
        # Create engine with AUTOCOMMIT (required for CREATE DATABASE)
        # SQL echo may include the CREATE LOGIN password literal. Keep SQL
        # statement logging disabled during bootstrap.
        engine = create_engine(sa_url, echo=False, isolation_level="AUTOCOMMIT")
        
        with engine.connect() as conn:
            # 1. Create Database if not exists
            result = conn.execute(text(f"SELECT 1 FROM sys.databases WHERE name = '{target_db}'"))
            if not result.scalar():
                logger.info("Uygulama veritabanı oluşturuluyor")
                conn.execute(text(f"CREATE DATABASE {target_db}"))
                logger.info("Uygulama veritabanı oluşturuldu")
            else:
                logger.info("Uygulama veritabanı zaten mevcut")

            # 2. Create User if not 'sa'
            if target_user and target_user.lower() != 'sa':
                logger.info("Uygulama veritabanı kullanıcısı denetleniyor")
                
                # Check if Login exists
                login_check = conn.execute(text(f"SELECT 1 FROM sys.server_principals WHERE name = '{target_user}'"))
                if not login_check.scalar():
                    logger.info("Uygulama veritabanı giriş hesabı oluşturuluyor")
                    # Create Login
                    conn.execute(text(f"CREATE LOGIN {target_user} WITH PASSWORD = '{target_password}'"))
                    logger.info("Uygulama veritabanı giriş hesabı oluşturuldu")
                
                # Switch to target database to create User and assign roles
                conn.execute(text(f"USE {target_db}"))
                
                # Check if User exists in DB
                user_check = conn.execute(text(f"SELECT 1 FROM sys.database_principals WHERE name = '{target_user}'"))
                if not user_check.scalar():
                    logger.info("Uygulama veritabanı kullanıcısı oluşturuluyor")
                    conn.execute(text(f"CREATE USER {target_user} FOR LOGIN {target_user}"))
                    conn.execute(text(f"ALTER ROLE db_owner ADD MEMBER {target_user}"))
                    logger.info("Uygulama veritabanı kullanıcısı ve rolü oluşturuldu")
                else:
                    logger.info("Uygulama veritabanı kullanıcısı zaten mevcut")

        engine.dispose()
    except Exception as exc:
        logger.warning(
            "Uygulama veritabanı veya kullanıcı denetlenemedi: %s; başlangıç akışı devam ediyor",
            type(exc).__name__,
        )

if __name__ == "__main__":
    # Only the database/login bootstrap runs here. Table schema is managed
    # by Alembic (`alembic upgrade head`, run next in entrypoint.sh) — see
    # docs/adr/ADR-0001-schema-migrations-alembic.md.
    create_database_and_user_if_not_exists()
