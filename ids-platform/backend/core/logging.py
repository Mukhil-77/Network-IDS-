"""
API-layer logging.

backend/utils/logger.py already gives every module a consistently-formatted
logger (see get_logger()); this module does two small, API-specific things
on top of it rather than duplicating that setup:

1. `configure_logging()` applies the *configured* (Settings.LOG_LEVEL) level
   to the already-initialized root logger - utils/logger.py reads the
   LOG_LEVEL environment variable directly at import time, which works for
   scripts but doesn't respect a `.env` file loaded via pydantic-settings;
   this makes the two consistent for the API process.
2. `log_access()` emits the one structured line per request the spec asks
   for (timestamp, client IP, prediction, confidence, latency, status code)
   - middleware.py calls this after each request completes. The timestamp
   is already part of every log line via utils/logger.py's formatter, so it
   isn't repeated as a field here.
"""

import logging
from typing import Optional

from backend.utils.logger import get_logger

_access_logger = get_logger("backend.api.access")


def configure_logging(log_level: str) -> None:
    """Apply `log_level` to the root logger, overriding whatever LOG_LEVEL was set to at import time."""
    logging.getLogger().setLevel(log_level.upper())
    _access_logger.info("Logging configured at level %s", log_level.upper())


def log_access(
    *,
    client_ip: str,
    method: str,
    path: str,
    status_code: int,
    latency_ms: float,
    request_id: str,
    prediction: Optional[str] = None,
    confidence: Optional[float] = None,
) -> None:
    """
    Emit one structured access-log line for a completed request.

    `prediction`/`confidence` are only populated for /predict calls that
    completed successfully - inference.py's own logging already covers the
    detailed pipeline view (see backend/ml/inference.py's "Prediction
    served: ..." line), so this line stays focused on the HTTP-transaction
    facts that only the API layer knows about (client IP, status code).
    """
    extra_fields = ""
    if prediction is not None:
        extra_fields = f" | prediction={prediction} | confidence={confidence}"

    _access_logger.info(
        "request_id=%s | client_ip=%s | %s %s | status=%d | latency_ms=%.3f%s",
        request_id,
        client_ip,
        method,
        path,
        status_code,
        latency_ms,
        extra_fields,
    )
