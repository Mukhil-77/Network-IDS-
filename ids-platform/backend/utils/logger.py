"""
Centralized logging configuration for the backend.

Every module should obtain its logger via `get_logger(__name__)` rather than
calling `logging.basicConfig` locally. This keeps log formatting consistent
across the whole project (preprocessing, training, the future API layer,
packet capture, etc.) and gives us one place to change the format, log level,
or output destination (e.g. adding a file handler or shipping to ELK later)
without touching every module.
"""

import logging
import os
import sys

# Log level is configurable via environment variable so it can be raised to
# DEBUG in development and kept at INFO (or WARNING) in production without
# any code changes.
_LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_configured = False


def _configure_root_logger() -> None:
    """Configure the root logger exactly once per process."""
    global _configured
    if _configured:
        return

    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(logging.Formatter(fmt=_LOG_FORMAT, datefmt=_DATE_FORMAT))

    root_logger = logging.getLogger()
    root_logger.setLevel(_LOG_LEVEL)
    root_logger.addHandler(handler)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """
    Return a configured logger for the given module name.

    Usage:
        logger = get_logger(__name__)
        logger.info("Loaded %d rows", len(df))
    """
    _configure_root_logger()
    return logging.getLogger(name)
