from __future__ import annotations

import logging
import os

import uvicorn

from app.core.logging import configure_logging
from app.db.migrations import upgrade_database
from app.main import create_app


def main() -> None:
    configure_logging()
    upgrade_database()

    host = os.getenv("APP_HOST", "127.0.0.1")
    port = int(os.getenv("APP_PORT", "8000"))
    logger = logging.getLogger("nanobot.sidecar")
    logger.info("starting sidecar backend on %s:%s", host, port)

    uvicorn.run(
        create_app(),
        host=host,
        port=port,
        log_level="info",
        access_log=False,
    )


if __name__ == "__main__":
    main()
