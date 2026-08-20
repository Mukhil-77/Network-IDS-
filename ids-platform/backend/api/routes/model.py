"""
Model endpoints.

    GET  /model/info            Currently-loaded model's metadata
    GET  /model/versions        Every trained version on disk, with its metrics
    POST /model/switch/{version}  Make a specific version the active model
    POST /model/train           Start a background training run for a family
    GET  /model/train/status    State of the background training run
    DELETE /model/{version}     Remove a trained version from disk
"""

from fastapi import APIRouter, Depends, HTTPException, status

from backend.auth.dependencies import get_current_user, require_permission
from backend.auth.models import User

from backend.api.schemas import (
    ModelDeleteResponse,
    ModelInfoResponse,
    ModelTrainRequest,
    ModelTrainStatusResponse,
    ModelVersionSummary,
)
from backend.ml.artifacts import ArtifactNotFoundError
from backend.ml.train_one import ALL_ALGORITHMS, available_families
from backend.services.prediction_service import prediction_service

router = APIRouter()


@router.get("/info", response_model=ModelInfoResponse, summary="Currently-loaded model's metadata")
async def model_info(user: User = Depends(get_current_user)) -> ModelInfoResponse:
    metadata = prediction_service.get_model_metadata()

    return ModelInfoResponse(
        model_name=metadata.model_name,
        version=metadata.model_version_dir or "unknown",
        training_date=metadata.training_date,
        accuracy=metadata.accuracy,
        num_features=len(metadata.features),
        pca_components=metadata.pca_components,
        sklearn_version=metadata.sklearn_version,
    )


@router.get("/versions", response_model=list[ModelVersionSummary], summary="List every trained model version on disk")
async def model_versions(user: User = Depends(get_current_user)) -> list[ModelVersionSummary]:
    return [ModelVersionSummary(**summary) for summary in prediction_service.list_model_versions()]


@router.post("/switch/{version}", response_model=ModelInfoResponse, summary="Activate a specific model version")
async def model_switch(version: str, user: User = Depends(get_current_user)) -> ModelInfoResponse:
    if not version.startswith("v"):
        version = f"v{version}"
    metadata = prediction_service.switch_model(version)
    return ModelInfoResponse(
        model_name=metadata.model_name,
        version=metadata.model_version_dir or version,
        training_date=metadata.training_date,
        accuracy=metadata.accuracy,
        num_features=len(metadata.features),
        pca_components=metadata.pca_components,
        sklearn_version=metadata.sklearn_version,
    )


@router.get("/train/status", response_model=ModelTrainStatusResponse, summary="State of the most recent background training run")
async def model_train_status(_: User = Depends(require_permission("model:train"))) -> ModelTrainStatusResponse:
    status = prediction_service.training_status()
    return ModelTrainStatusResponse(**status)


@router.post("/train", response_model=ModelTrainStatusResponse, status_code=status.HTTP_202_ACCEPTED, summary="Start a background training run for one algorithm family")
async def model_train(
    payload: ModelTrainRequest,
    _: User = Depends(require_permission("model:train")),
) -> ModelTrainStatusResponse:
    if payload.algorithm not in available_families() and payload.algorithm != ALL_ALGORITHMS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown algorithm family '{payload.algorithm}'. Valid choices: {available_families()} or '{ALL_ALGORITHMS}'",
        )

    started = prediction_service.train_model(payload.algorithm)
    if not started:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A training run is already in progress",
        )
    return ModelTrainStatusResponse(**prediction_service.training_status())


@router.post("/train/cancel", response_model=ModelTrainStatusResponse, summary="Stop the background training run at its next checkpoint")
async def model_train_cancel(
    _: User = Depends(require_permission("model:train")),
) -> ModelTrainStatusResponse:
    prediction_service.cancel_training()
    return ModelTrainStatusResponse(**prediction_service.training_status())


@router.delete("/{version}", response_model=ModelDeleteResponse, summary="Delete a trained model version")
async def model_delete(
    version: str,
    _: User = Depends(require_permission("model:train")),
) -> ModelDeleteResponse:
    if not version.startswith("v"):
        version = f"v{version}"
    try:
        result = prediction_service.delete_model(version)
    except ArtifactNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return ModelDeleteResponse(**result)
