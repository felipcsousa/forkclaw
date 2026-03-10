from __future__ import annotations

import logging
from pathlib import Path

from app.core.config import get_settings


def configure_logging() -> Path:
    settings = get_settings()
    settings.ensure_data_dir()
    log_path = settings.logs_dir / "backend.log"

    root_logger = logging.getLogger()
    if getattr(root_logger, "_nanobot_configured", False):
        return log_path

    handlers = [
        logging.FileHandler(log_path, encoding="utf-8"),
        logging.StreamHandler(),
    ]
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=handlers,
        force=True,
    )
    setattr(root_logger, "_nanobot_configured", True)
    return log_path
