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
    parser.add_argument("--username", help="Yalnızca yeni kullanıcı oluşturulacaksa gerekir")
    return parser.parse_args()


async def _run(args: argparse.Namespace) -> None:
    app_db = AppDatabase()
    try:
        password: str | None = None
        if args.username:
            password = getpass.getpass("Yeni OWNER parolası: ")
            confirmation = getpass.getpass("Yeni OWNER parolası (tekrar): ")
            if password != confirmation:
                raise ValueError("Parolalar eşleşmiyor.")

        user_id, changed = await bootstrap_owner(
            app_db,
            email=args.email,
            username=args.username,
            password=password,
        )
        logger.info(
            "OWNER bootstrap tamamlandı: user_id=%s changed=%s",
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
        logger.critical("OWNER bootstrap başarısız: %s", exc)
        raise SystemExit(1) from exc
    except Exception as exc:
        logger.critical("OWNER bootstrap başarısız: %s", type(exc).__name__)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
