"""
Prediction service.

This is deliberately thin - every real decision (validation rules,
confidence scoring, severity mapping, model loading/caching) already lives
in backend/ml/ (Milestones 2-3) and is reused as-is. This class exists only
to:

    1. Bind backend.ml.predictor's `models_dir` parameter to the app's
       configured Settings.MODEL_PATH, so route handlers never hardcode a path.
    2. Give the API layer one narrow, mockable seam (this class) instead of
       every route importing backend.ml.predictor/inference directly - useful
       for testing (see tests/test_api_predict.py) and for Milestone 5+ when
       this is the natural place to add e.g. request-level caching.

No validation, confidence, or severity logic is reimplemented here - it all
flows straight through to backend.ml.inference.predict().
"""

from __future__ import annotations

from pathlib import Path

from backend.ml import artifacts, inference
from backend.ml.artifacts import ArtifactNotFoundError
from backend.ml.predictor import Predictor, get_predictor, reload_predictor, reset_predictor
from backend.ml.schemas import ModelMetadata, PredictionResponse
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class PredictionService:
    def __init__(self, models_dir: str):
        self.models_dir = models_dir

    def startup(self) -> None:
        """
        Called once at app startup (see backend/main.py's lifespan) to warm
        the model cache. Deliberately does not raise if no model is
        available yet - the API should still come up so /health can report
        a clear "model unavailable" status rather than the process failing
        to start at all (e.g. before the very first training run).
        """
        try:
            predictor = get_predictor(models_dir=self.models_dir)
            logger.info(
                "Prediction service ready: model_version=%s, model=%s",
                predictor.version_label,
                type(predictor.model).__name__,
            )
        except ArtifactNotFoundError:
            logger.warning(
                "No trained model found under '%s' at startup; /predict and "
                "/model/info will return 404 until a model is trained and saved.",
                self.models_dir,
            )

    def _active_predictor(self) -> Predictor:
        """
        Raises ArtifactNotFoundError if no model version exists yet - callers
        (routes) let this propagate; the registered exception handler turns
        it into a 404.
        """
        return get_predictor(models_dir=self.models_dir)

    def is_model_loaded(self) -> bool:
        try:
            self._active_predictor()
            return True
        except ArtifactNotFoundError:
            return False

    def predict(self, features: dict) -> PredictionResponse:
        """
        Run one feature dict through the full detection pipeline.

        Raises (propagated straight from backend.ml.inference.predict, see
        that module's docstring for the full contract):
            ArtifactNotFoundError:     no model available -> 404
            FeatureValidationFailed:   invalid feature values -> 422
            InferencePipelineError:    pipeline failed post-validation -> 500
        """
        predictor = self._active_predictor()
        return inference.predict(features, predictor=predictor)

    def get_model_metadata(self) -> ModelMetadata:
        """Raises ArtifactNotFoundError if no model is available -> 404."""
        predictor = self._active_predictor()
        return predictor.as_metadata_model()

    def get_expected_features(self) -> list[str]:
        """
        The trained model's exact required raw input feature names/order
        (Predictor.expected_features). Added for Milestone 5:
        backend.packet_capture.feature_mapper reindexes live-computed flow
        features against this list. Raises ArtifactNotFoundError if no
        model is available.
        """
        return self._active_predictor().expected_features

    def list_model_versions(self) -> list[dict]:
        """
        Summarize every trained model version on disk (models/vN dirs), one
        dict per version: {"version", "model_name", "dataset", "training_date",
        "accuracy", "pca_components", "active"}. Never raises - no models at
        all yields an empty list, so the API can show an honest "no models
        trained yet" state.
        """
        summaries: list[dict] = []
        active_version = None
        try:
            active_version = self._active_predictor().version_label
        except ArtifactNotFoundError:
            pass

        for version_num in artifacts.list_versions(self.models_dir):
            version_dir = Path(self.models_dir) / f"v{version_num}"
            try:
                metadata = artifacts.load_metadata(version_dir)
            except ArtifactNotFoundError:
                continue  # half-written/cleared version dir - skip, don't crash
            summaries.append(
                {
                    "version": f"v{version_num}",
                    "model_name": metadata.get("model_name", "unknown"),
                    "dataset": metadata.get("dataset", "unknown"),
                    "training_date": metadata.get("training_date", ""),
                    "accuracy": metadata.get("accuracy"),
                    "pca_components": metadata.get("pca_components"),
                    "active": f"v{version_num}" == active_version,
                }
            )
        return summaries

    def switch_model(self, version: str) -> ModelMetadata:
        """
        Load a specific model version (e.g. "v2") as the active predictor.

        Raises:
            ArtifactNotFoundError: If `version` names no existing version dir
                (or its bundle is incomplete) -> 404 via the exception handler.
        """
        version_dir = Path(self.models_dir) / version
        if not version_dir.is_dir():
            raise ArtifactNotFoundError(f"No model version directory found: {version_dir}")
        predictor = reload_predictor(version_dir=version_dir)
        logger.info(
            "Switched active model to %s (%s)",
            predictor.version_label,
            type(predictor.model).__name__,
        )
        return predictor.as_metadata_model()

    def reset_models(self) -> list[str]:
        """
        Delete every trained model version directory and clear the predictor
        cache, so the platform returns to the "no model trained yet" state.
        Returns the list of version labels that were removed.
        """
        removed = []
        for version_num in artifacts.list_versions(self.models_dir):
            version_dir = Path(self.models_dir) / f"v{version_num}"
            for file in list(version_dir.iterdir()):
                file.unlink()
            version_dir.rmdir()
            removed.append(f"v{version_num}")
        reset_predictor()
        logger.info("Reset models: removed %s", removed or ["<none>"])
        return removed


# --------------------------------------------------------------------------
# Process-wide instance, bound to configured settings. Routes import this
# directly (`from backend.services.prediction_service import prediction_service`)
# rather than constructing their own - mirrors backend.ml.predictor's own
# singleton pattern, and keeps main.py free of import-order issues since
# nothing here imports from backend.api or backend.main.
# --------------------------------------------------------------------------

from backend.core.config import get_settings  # noqa: E402  (after class definition, to avoid a partial-import cycle)

prediction_service = PredictionService(models_dir=get_settings().MODEL_PATH)
