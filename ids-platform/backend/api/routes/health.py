"""
GET /health

Deliberately never raises or returns a non-200 status - a health check's
job is to report status, not to fail. A missing model is reflected in the
response body (`model_status: "unavailable"`, overall `status: "degraded"`),
not as a 404 - 404 is reserved for endpoints that actually need the model
to do their job (/predict, /model/info; see backend/core/exception_handlers.py).
"""

import time

from fastapi import APIRouter, Request

from backend.api.schemas import HealthResponse
from backend.core.config import get_settings
from backend.services.prediction_service import prediction_service

router = APIRouter()


@router.get("/health", response_model=HealthResponse, summary="API and model health status")
async def health(request: Request) -> HealthResponse:
    settings = get_settings()
    model_loaded = prediction_service.is_model_loaded()

    start_time = getattr(request.app.state, "start_time", time.time())
    uptime_seconds = time.time() - start_time

    return HealthResponse(
        status="healthy" if model_loaded else "degraded",
        model_status="loaded" if model_loaded else "unavailable",
        version=settings.API_VERSION,
        uptime_seconds=round(uptime_seconds, 3),
    )
