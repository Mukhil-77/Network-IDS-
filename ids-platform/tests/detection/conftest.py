"""
Fixtures scoped to tests/detection/. Inherits `trained_model_dir` from the
parent tests/conftest.py (Milestone 3's fixture) without modifying that file.
"""

import pytest

from backend.services.prediction_service import PredictionService


@pytest.fixture
def prediction_service_with_model(trained_model_dir) -> PredictionService:
    """A PredictionService instance pointed at the synthetic trained model."""
    return PredictionService(models_dir=str(trained_model_dir.parent))


@pytest.fixture
def prediction_service_without_model(tmp_path) -> PredictionService:
    """A PredictionService pointed at an empty directory - no model available."""
    return PredictionService(models_dir=str(tmp_path / "no_model_here"))
