"""Block until the application database accepts connections, or fail loudly.

Split out of `create_db.py` (P1-13). `create_db.py` used to be both the
readiness probe and the bootstrap step, and it caught every exception and
logged a warning instead of raising — so `entrypoint.sh`'s retry loop saw
"success" on the very first attempt even when SQL Server was not up yet,
proceeded straight to `alembic upgrade head`, and that failed hard instead.
This script does one job: return exit code 0 once a real connection succeeds,
non-zero otherwise, so the shell retry loop actually retries.
"""
import logging
import sys

from sqlalchemy import create_engine, make_url, text

from app_database.config import DATABASE_URL
from common.logging_config import setup_logging

setup_logging()
logger = logging.getLogger(__name__)


def wait_once() -> bool:
    """Return True if the application database answered a real query."""
    try:
        url = make_url(DATABASE_URL)
        # Connect to the server, not the application database itself: the
        # database or login this URL names may not exist yet on a first-time
        # install, and that has to read as "not ready" the same as an
        # unreachable server, not as a fatal error worth aborting on.
        probe_url = url.set(database="master", drivername="mssql+pyodbc")
        engine = create_engine(probe_url, echo=False)
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        finally:
            engine.dispose()
    except Exception as exc:
        logger.info("Veritabanı henüz hazır değil: %s", type(exc).__name__)
        return False


if __name__ == "__main__":
    sys.exit(0 if wait_once() else 1)
