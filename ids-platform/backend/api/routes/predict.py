"""
POST /predict

Request/response bodies are backend.ml.schemas.PredictionRequest and
.PredictionResponse directly - the exact same Pydantic models
inference.py/predictor.py already speak in (see that module's docstring).
No wrapping or field-renaming schema is introduced here: doing so would
mean maintaining a second copy of a contract that already exists, exactly
the duplication Milestone 4 is scoped to avoid.

    Request
      v
    FastAPI body validation against PredictionRequest   -> 400 if malformed
      v
    prediction_service.predict()
      v
    backend.ml.validator                                -> 422 if invalid
      v
    backend.ml.predictor (scaler -> PCA -> model)        -> 404 if no model,
      v                                                     500 if pipeline fails
    backend.ml.confidence + backend.ml.severity
      v
    PredictionResponse
"""

from fastapi import APIRouter, Depends, Request

from backend.auth.dependencies import require_permission
from backend.auth.models import User
from backend.ml.schemas import PredictionRequest, PredictionResponse
from backend.services.prediction_service import prediction_service

router = APIRouter()


@router.post(
    "/predict",
    response_model=PredictionResponse,
    summary="Classify one network flow's features",
    responses={
        404: {"description": "No trained model is currently available."},
        422: {"description": "Feature values are missing, unexpected, or invalid (NaN/infinite/non-numeric)."},
    },
)
async def predict(payload: PredictionRequest, request: Request, user: User = Depends(require_permission("predict:execute"))) -> PredictionResponse:
    response = prediction_service.predict(payload.features)

    # Stashed on request.state (not read from the response body) so
    # RequestLoggingMiddleware can include prediction/confidence in its one
    # access-log line without re-parsing/duplicating the response - see
    # backend/core/middleware.py.
    request.state.prediction_label = response.prediction
    request.state.prediction_confidence = response.confidence

    return response
