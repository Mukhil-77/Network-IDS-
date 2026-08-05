"""
Middleware stack.

Order matters - Starlette applies middleware in the order they're added to
the outermost layer first, so RequestIDMiddleware is added last (making it
run first) so every other middleware and the route handler itself can rely
on `request.state.request_id` already being set.

    add_middleware(CORS)              <- runs 4th (innermost, closest to route)
    add_middleware(RateLimitPlaceholder) <- runs 3rd
    add_middleware(ProcessingTime)    <- runs 2nd
    add_middleware(RequestID)         <- runs 1st (outermost)
"""

from __future__ import annotations

import time
import uuid

from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware

from backend.core.config import Settings
from backend.core.logging import log_access


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Attaches a unique request_id to every request (state + response header), for log correlation."""

    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class ProcessingTimeMiddleware(BaseHTTPMiddleware):
    """Measures total request handling time and exposes it as an X-Process-Time-Ms response header."""

    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000
        request.state.processing_time_ms = elapsed_ms
        response.headers["X-Process-Time-Ms"] = f"{elapsed_ms:.3f}"
        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Emits one structured access-log line per request via
    backend.core.logging.log_access(), after the response is ready.

    Relies on RequestIDMiddleware and ProcessingTimeMiddleware having
    already run (see registration order in setup_middleware() below) so
    `request.state.request_id` / `.processing_time_ms` are populated.

    Prediction/confidence enrichment for /predict calls is read off
    `request.state`, which backend/api/routes/predict.py sets after a
    successful prediction - this middleware never inspects the response
    body directly (streaming bodies can only be consumed once, and doing
    so here would break the actual response to the client).
    """

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        log_access(
            client_ip=client_ip,
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            latency_ms=getattr(request.state, "processing_time_ms", 0.0),
            request_id=getattr(request.state, "request_id", "unknown"),
            prediction=getattr(request.state, "prediction_label", None),
            confidence=getattr(request.state, "prediction_confidence", None),
        )
        return response


class RateLimitPlaceholderMiddleware(BaseHTTPMiddleware):
    """
    Placeholder only - per Milestone 4 scope, real rate limiting (e.g.
    token bucket per API key/IP, backed by Redis) is out of scope and
    deferred to a future milestone.

    Currently a no-op that passes every request through unchanged. Kept as
    real middleware (rather than just a comment) so the position it will
    occupy in the stack, and the `ENABLE_RATE_LIMIT` config switch that
    will gate it, are both already in place - enabling real rate limiting
    later is then a matter of filling in `dispatch()`, not restructuring
    the app.
    """

    async def dispatch(self, request: Request, call_next):
        # TODO(future milestone): enforce a per-client request budget here
        # when settings.ENABLE_RATE_LIMIT is True; return 429 if exceeded.
        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Standard defensive response headers - none of these require any
    request-specific logic, so they're set unconditionally on every
    response. `Strict-Transport-Security` is included even though this app
    doesn't terminate TLS itself (that's normally a reverse proxy's job) -
    harmless to send and correct once one sits in front of this app.
    """

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        return response


def setup_middleware(app: FastAPI, settings: Settings) -> None:
    """Register the full middleware stack on `app`, in the order described in this module's docstring."""

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RateLimitPlaceholderMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(ProcessingTimeMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(RequestIDMiddleware)
