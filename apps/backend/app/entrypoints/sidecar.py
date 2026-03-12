from __future__ import annotations

import logging
import os

import uvicorn

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.migrations import upgrade_database
from app.main import create_app
from app.services.runtime_supervisor import RuntimeSupervisor


def main() -> None:
    configure_logging()
    upgrade_database()

    host = os.getenv("APP_HOST", "127.0.0.1")
    port = int(os.getenv("APP_PORT", "8000"))
    logger = logging.getLogger("nanobot.sidecar")
    logger.info("starting sidecar backend on %s:%s", host, port)
    server: uvicorn.Server | None = None

    def shutdown_callback() -> None:
        nonlocal server
        if server is not None:
            server.should_exit = True

    app = create_app(
        shutdown_callback=shutdown_callback,
        runtime_supervisor=RuntimeSupervisor(get_settings()),
    )
    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level="info",
        access_log=False,
    )
    server = uvicorn.Server(config)
    server.run()


if __name__ == "__main__":
    main()
