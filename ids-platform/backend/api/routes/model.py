"""
Model endpoints.

    GET  /model/info            Currently-loaded model's metadata
    GET  /model/versions        Every trained version on disk, with its metrics
    POST /model/switch/{version}  Make a specific version the active model
"""

from fastapi import APIRouter, Depends

from backend.auth.dependencies import get_current_user
from backend.auth.models import User

from backend.api.schemas import ModelInfoResponse, ModelVersionSummary
from backend.ml.artifacts import ArtifactNotFoundError
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
