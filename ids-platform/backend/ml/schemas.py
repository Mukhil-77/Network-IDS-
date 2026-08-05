"""
Pydantic models for the prediction service.

These are the data contracts every other Milestone 3 module speaks in:
validator.py raises errors shaped like ValidationErrorDetail, inference.py
returns a PredictionResponse, predictor.py exposes its loaded metadata as
ModelMetadata. Keeping them in one file (rather than scattered dataclasses
per module) means Milestone 4's FastAPI layer can import this file directly
as its request/response models with zero translation layer.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class PredictionRequest(BaseModel):
    """
    A single flow's raw feature values, keyed by the same column names the
    model was trained on (i.e. `predictor.expected_features` /
    `scaler.feature_names_in_` - the post-preprocessing, pre-scaling CIC-IDS2017
    feature columns, NOT the PCA components).

    Deliberately a free-form dict rather than one Pydantic field per feature:
    CIC-IDS2017 has ~70 feature columns, and hardcoding each one as a
    Pydantic field would silently go stale the moment feature engineering
    changes. validator.py is the actual source of truth for "is this a
    valid feature set" - this schema only enforces the outer shape.
    """

    features: dict[str, float] = Field(
        ...,
        description="Raw feature name -> value, matching the trained pipeline's expected input columns.",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "features": {
                    "Flow Duration": 121_212.0,
                    "Total Fwd Packets": 12.0,
                    "Total Backward Packets": 8.0,
                    "Flow Bytes/s": 3541.2,
                    "Flow Packets/s": 98.7,
                }
            }
        }
    }


class PredictionResponse(BaseModel):
    """The result of running one PredictionRequest through the full pipeline."""

    prediction: str = Field(..., description="Predicted attack type, e.g. 'DoS', 'BENIGN'.")
    confidence: float = Field(..., ge=0.0, le=100.0, description="Model confidence as a percentage (0-100).")
    severity: str = Field(..., description="Severity bucket for `prediction`: Low, Medium, High, or Critical.")
    model_version: str = Field(..., description="Version directory the serving model was loaded from, e.g. 'v1'.")
    latency_ms: float = Field(..., ge=0.0, description="End-to-end inference latency in milliseconds.")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="UTC timestamp the prediction was made.",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "prediction": "DoS",
                "confidence": 98.42,
                "severity": "High",
                "model_version": "v1",
                "latency_ms": 4.31,
                "timestamp": "2026-07-23T10:15:00+00:00",
            }
        }
    }


class ValidationErrorDetail(BaseModel):
    """One specific problem found with a PredictionRequest's features."""

    field: str = Field(..., description="Feature name the problem relates to, or '__root__' for request-level issues.")
    error_type: str = Field(
        ...,
        description="Machine-readable category: missing_feature, unexpected_feature, invalid_type, "
        "nan_value, infinite_value, feature_order.",
    )
    message: str = Field(..., description="Human-readable explanation.")


class ValidationErrorResponse(BaseModel):
    """The full set of problems found with one PredictionRequest, returned instead of a prediction."""

    error: str = Field(default="validation_error")
    detail: list[ValidationErrorDetail]

    @field_validator("detail")
    @classmethod
    def _must_have_at_least_one_error(cls, v: list[ValidationErrorDetail]) -> list[ValidationErrorDetail]:
        if not v:
            raise ValueError("ValidationErrorResponse.detail must contain at least one error")
        return v


class ModelMetadata(BaseModel):
    """
    Mirrors artifacts.build_metadata()'s metadata.json schema exactly, so a
    loaded model version's provenance can be returned to a caller (or a
    future /health or /model-info API endpoint) without reshaping.
    """

    model_name: str
    dataset: str
    training_date: str
    accuracy: float
    precision: float
    recall: float
    f1_score: float
    features: list[str]
    pca_components: int
    sklearn_version: str
    project_version: str
    model_version_dir: Optional[str] = Field(
        default=None, description="Which models/vN directory this metadata was loaded from."
    )
