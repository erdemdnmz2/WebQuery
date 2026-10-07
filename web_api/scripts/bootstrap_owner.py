"""Create or promote a platform OWNER without exposing this trust root over HTTP."""

import argparse
import asyncio
import getpass
import logging

from app_database.app_database import AppDatabase
from common.logging_config import setup_logging
from owner.bootstrap import bootstrap_owner

logger = logging.getLogger(__name__)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="WebQuery platform OWNER bootstrap")
    parser.add_argument("--email", required=True, help="Mevcut veya yeni OWNER e-posta adresi")
    parser.add_argument("--username", help="Required only when creating a new user")
    return parser.parse_args()


async def _run(args: argparse.Namespace) -> None:
    app_db = AppDatabase()
    try:
        password: str | None = None
        if args.username:
            password = getpass.getpass("New OWNER password: ")
            confirmation = getpass.getpass("New OWNER password (again): ")
            if password != confirmation:
                raise ValueError("Passwords do not match.")

        user_id, changed = await bootstrap_owner(
            app_db,
            email=args.email,
            username=args.username,
            password=password,
        )
        logger.info(
            "OWNER bootstrap complete: user_id=%s changed=%s",
            user_id,
            changed,
        )
    finally:
        await app_db.app_engine.dispose()


def main() -> None:
    setup_logging()
    try:
        asyncio.run(_run(_arguments()))
    except ValueError as exc:
        logger.critical("OWNER bootstrap failed: %s", exc)
        raise SystemExit(1) from exc
    except Exception as exc:
        logger.critical("OWNER bootstrap failed: %s", type(exc).__name__)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
