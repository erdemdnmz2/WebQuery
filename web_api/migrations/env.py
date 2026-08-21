"""
Alembic environment.

Runs synchronously — SQLAlchemy's async engines are not needed here, and
Alembic's own async support adds complexity this project doesn't use.
The app's connection string is built for an async driver
(aioodbc/asyncpg/aiomysql/aiosqlite); this file rewrites it to the matching
sync driver before handing it to Alembic.

See docs/adr/ADR-0001-schema-migrations-alembic.md for why this exists.
"""
import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# Make `app_database` (and any other web_api package) importable regardless
# of the working directory Alembic was invoked from.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Importing this module resolves DATABASE_URL the same way the application
# does (dotenv loading + APP_DATABASE_URL override + per-part defaults) —
# duplicating that logic here would drift from app_database/config.py.
from app_database.config import DATABASE_URL
from app_database.models import Base

target_metadata = Base.metadata

config = context.config


def _to_sync_url(async_url: str) -> str:
    """Rewrites an async SQLAlchemy URL to its sync-driver equivalent."""
    return (
        async_url.replace("+aioodbc", "+pyodbc")
        .replace("+asyncpg", "+psycopg2")
        .replace("+aiomysql", "+pymysql")
        .replace("+aiosqlite", "")
    )


config.set_main_option("sqlalchemy.url", _to_sync_url(DATABASE_URL))

if config.config_file_name:
    fileConfig(config.config_file_name)


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
