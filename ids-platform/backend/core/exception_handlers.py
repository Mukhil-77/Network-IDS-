"""
Exception -> HTTP response mapping.

Every exception type backend.ml can raise is caught exactly once, here, and
turned into the status code the spec requires. Route handlers
(backend/api/routes/*.py) do not catch these themselves - they let
exceptions propagate and stay focused on request/response wiring, which
also means every route gets identical error formatting for free.

    400  RequestValidationError        malformed request body (wrong shape/type
                                        at the HTTP/schema level, before it
                                        ever reaches backend.ml)
    404  ArtifactNotFoundError,        no model artifacts available to serve
         ModelNotLoadedError
    422  FeatureValidationFailed       well-formed request, but feature values
                                        are semantically invalid (missing,
                                        unexpected, NaN, infinite, wrong type)
    500  InferencePipelineError,       the model/scaler/PCA pipeline itself
         Exception (catch-all)         failed, or anything unanticipated

This 400-vs-422 split follows the distinction the two status codes were
defined for: 400 is "the request I sent doesn't even match the expected
shape"; 422 is "the request is shaped correctly, but its content isn't
valid" - which maps exactly onto validator.py's job (checking feature
*values*) versus FastAPI/Pydantic's request-schema validation.
"""

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from backend.ml.artifacts import ArtifactNotFoundError
from backend.ml.inference import FeatureValidationFailed, InferencePipelineError
from backend.ml.predictor import ModelNotLoadedError

logger = logging.getLogger("backend.api.errors")


def _error_body(error: str, detail) -> dict:
    return {"error": error, "detail": detail}


async def handle_request_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    logger.warning("Malformed request body on %s: %s", request.url.path, exc.errors())
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=_error_body("validation_error", exc.errors()),
    )


async def handle_feature_validation_failed(request: Request, exc: FeatureValidationFailed) -> JSONResponse:
    logger.warning("Invalid feature input on %s: %d error(s)", request.url.path, len(exc.errors))
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=_error_body("invalid_input", [e.model_dump() for e in exc.errors]),
    )


async def handle_model_missing(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Model unavailable while handling %s: %s", request.url.path, exc)
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content=_error_body("model_missing", str(exc)),
    )


async def handle_inference_pipeline_error(request: Request, exc: InferencePipelineError) -> JSONResponse:
    logger.exception("Inference pipeline error on %s", request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=_error_body("internal_error", "Prediction failed due to an internal error."),
    )


async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception on %s", request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=_error_body("internal_error", "An unexpected error occurred."),
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(RequestValidationError, handle_request_validation_error)
    app.add_exception_handler(FeatureValidationFailed, handle_feature_validation_failed)
    app.add_exception_handler(ArtifactNotFoundError, handle_model_missing)
    app.add_exception_handler(ModelNotLoadedError, handle_model_missing)
    app.add_exception_handler(InferencePipelineError, handle_inference_pipeline_error)
    app.add_exception_handler(Exception, handle_unexpected_error)
