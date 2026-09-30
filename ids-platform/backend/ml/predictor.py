"""
Singleton loader/cache for the trained inference pipeline: model + scaler + PCA.

The deployed model operates on PCA-transformed features (35 components).
The full pipeline is: Raw features (70) → Scaler → PCA (35 components) → Model.

Everything in backend/ml/{validator,confidence,severity,inference}.py reads
from this module rather than touching backend/ml/artifacts.py directly, so
the (relatively slow) disk load - unpickling model/scaler/PCA - happens
exactly once per process.

Thread-safety note: the *loading* step (get_predictor() the first time it's
called) is protected by a lock using double-checked locking, since multiple
request-handling threads could race to initialize the singleton. *Using*
an already-loaded Predictor (calling .predict() on its cached pipeline) needs
no additional locking - scikit-learn's transform/predict methods don't mutate
estimator state, so concurrent reads from multiple threads are safe.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from backend.ml import artifacts
from backend.ml.schemas import ModelMetadata
from backend.ml.feature_schema import CANONICAL_FEATURE_NAMES
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class ModelNotLoadedError(RuntimeError):
    """Raised when inference is attempted before a model has been successfully loaded."""


class Predictor:
    """
    Holds one fully-loaded model version in memory: the fitted model,
    scaler, PCA, and the raw feature names the scaler expects.
    
    The pipeline can be either:
        Raw features (N) → Scaler → Model (no PCA)
        Raw features (N) → Scaler → PCA (M components) → Model
    
    Not meant to be constructed directly - use get_predictor() to get the
    process-wide singleton instance.
    """

    def __init__(self, version_dir: str | Path):
        self.version_dir = Path(version_dir)
        self.version_label = self.version_dir.name  # e.g. "v1"

        bundle = artifacts.load_model_bundle(self.version_dir)
        self.model = bundle["model"]
        self.scaler = bundle["scaler"]
        self.pca = bundle["pca"]
        self.metadata: dict = bundle["metadata"]

        # The raw feature names the scaler expects (from the training data)
        # These come from the scaler's feature_names_in_ which matches the
        # training data columns (70 features from CIC-IDS2017)
        if hasattr(self.scaler, "feature_names_in_"):
            self.raw_feature_names: list[str] = list(self.scaler.feature_names_in_)
        else:
            # Fallback: use the feature_names.json from the bundle
            self.raw_feature_names = bundle.get("feature_names", [])

        # PCA component names (PC1, PC2, ...)
        self.pca_components = self.metadata.get("pca_components", 35)
        self.pca_feature_names = [f"PC{i+1}" for i in range(self.pca_components)]

        # Detect whether this model uses PCA or works directly on scaled features
        # Check if model's expected features match scaler features (no PCA) or PCA components
        self._uses_pca = True
        if hasattr(self.model, "feature_names_in_"):
            model_features = list(self.model.feature_names_in_)
            if set(model_features) == set(self.raw_feature_names):
                self._uses_pca = False
                logger.info("Model uses scaled features directly (no PCA)")
            elif set(model_features) == set(self.pca_feature_names):
                self._uses_pca = True
                logger.info("Model uses PCA components")
            else:
                logger.warning(
                    "Model feature names (%d) don't match scaler features (%d) or PCA components (%d). "
                    "Model: %s, Scaler: %s, Expected PCA: %s",
                    len(model_features), len(self.raw_feature_names), len(self.pca_feature_names),
                    sorted(model_features)[:5], sorted(self.raw_feature_names)[:5], sorted(self.pca_feature_names)[:5]
                )
        else:
            # Fallback: compare number of features
            n_raw = len(self.raw_feature_names)
            n_pca = self.pca_components
            # If model expects same number as raw features, no PCA
            if hasattr(self.model, 'n_features_in_'):
                if self.model.n_features_in_ == n_raw:
                    self._uses_pca = False
                elif self.model.n_features_in_ == n_pca:
                    self._uses_pca = True
            elif hasattr(self.model, 'num_feature'):
                if self.model.num_feature() == n_raw:
                    self._uses_pca = False
                elif self.model.num_feature() == n_pca:
                    self._uses_pca = True

        logger.info(
            "Predictor loaded: version=%s, model=%s, raw_features=%d, pca_components=%d, uses_pca=%s",
            self.version_label,
            type(self.model).__name__,
            len(self.raw_feature_names),
            self.pca_components,
            self._uses_pca,
        )

    def _is_lightgbm(self) -> bool:
        """Check if the model is a LightGBM Booster."""
        return type(self.model).__name__ == 'Booster'

    def _transform(self, X: pd.DataFrame) -> np.ndarray:
        """
        Apply the full preprocessing pipeline: scaler → PCA (if needed).
        
        Args:
            X: DataFrame with raw feature columns matching scaler's expected input.
            
        Returns:
            Transformed array ready for the model (scaled, or scaled+PCA).
        """
        # Ensure columns match scaler's expected input
        if list(X.columns) != self.raw_feature_names:
            missing = set(self.raw_feature_names) - set(X.columns)
            extra = set(X.columns) - set(self.raw_feature_names)
            if missing:
                raise ValueError(f"Missing raw features for scaler: {missing}")
            if extra:
                raise ValueError(f"Extra raw features not expected by scaler: {extra}")
            if list(X.columns) != self.raw_feature_names:
                X = X[self.raw_feature_names]
        
        # Apply scaler
        X_scaled = self.scaler.transform(X)
        
        # Apply PCA only if model expects it
        if self._uses_pca:
            X_pca = self.pca.transform(X_scaled)
            return X_pca
        else:
            return X_scaled

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """
        Predict on raw features by applying the full pipeline: scaler → PCA → model.
        
        Args:
            X: DataFrame with exactly the raw feature columns the scaler expects.
            
        Returns:
            Predicted class labels as numpy array.
        """
        X_pca = self._transform(X)
        
        if self._is_lightgbm():
            # LightGBM Booster.predict() returns probabilities, need argmax for labels
            probas = self.model.predict(X_pca)
            return np.argmax(probas, axis=1)
        else:
            preds = self.model.predict(X_pca)
            # Ensure we return 1D array of class indices
            if preds.ndim > 1:
                return np.argmax(preds, axis=1)
            return preds
    
    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """
        Predict class probabilities on raw features by applying the full pipeline.
        
        Args:
            X: DataFrame with exactly the raw feature columns the scaler expects.
            
        Returns:
            Predicted probabilities as numpy array (n_samples, n_classes).
        """
        X_pca = self._transform(X)
        
        if self._is_lightgbm():
            # LightGBM Booster.predict() returns probabilities directly
            return self.model.predict(X_pca)
        elif hasattr(self.model, 'predict_proba'):
            return self.model.predict_proba(X_pca)
        else:
            # Fallback: return uniform probabilities
            n_samples = X_pca.shape[0]
            n_classes = len(self.metadata.get('features', [1, 2]))
            return np.ones((n_samples, n_classes)) / n_classes

    def decode_label(self, raw_prediction) -> str:
        """
        Translate a raw model output into a human-readable attack label.
        
        Since the model is trained directly on string labels, the raw
        prediction is already the label.
        """
        # Handle array input - extract scalar if it's a 0-d or 1-d array
        if hasattr(raw_prediction, '__len__') and not isinstance(raw_prediction, str):
            if hasattr(raw_prediction, 'ndim') and raw_prediction.ndim > 0:
                raw_prediction = raw_prediction.flatten()[0] if raw_prediction.size > 0 else 0
            elif len(raw_prediction) > 0:
                raw_prediction = raw_prediction[0]
            else:
                raw_prediction = 0
        
        # Handle LightGBM label mapping
        if self._is_lightgbm():
            # For LightGBM, we get class indices (0, 1), need to map to labels
            label_mapping = self.metadata.get('label_mapping', {0: 'dos', 1: 'normal'})
            # JSON converts int keys to strings, handle both
            key = int(raw_prediction)
            if key in label_mapping:
                return label_mapping[key]
            if str(key) in label_mapping:
                return label_mapping[str(key)]
            return 'unknown'
        return str(raw_prediction)

    def as_metadata_model(self) -> ModelMetadata:
        """Return this predictor's metadata.json contents as a validated ModelMetadata."""
        return ModelMetadata(**self.metadata, model_version_dir=self.version_label)


# --------------------------------------------------------------------------
# Process-wide singleton
# --------------------------------------------------------------------------

_predictor: Optional[Predictor] = None
_predictor_lock = threading.Lock()
_loaded_version_dir: Optional[str] = None


def get_predictor(version_dir: Optional[str | Path] = None, models_dir: str | Path = "models") -> Predictor:
    """
    Return the process-wide Predictor singleton, loading it on first call.

    Thread-safe: uses double-checked locking so concurrent first callers
    (e.g. multiple FastAPI workers/threads starting up together in
    Milestone 4) don't each unpickle the model independently.

    Args:
        version_dir: Exact model version directory to load (e.g.
            "models/v2"). Defaults to the highest existing version under
            `models_dir`.
        models_dir: Root directory containing versioned model subfolders,
            used only when `version_dir` is not given.

    Returns:
        The loaded (and cached) Predictor.

    Raises:
        artifacts.ArtifactNotFoundError: If no model version exists, or a
            required artifact file is missing from it.
    """
    global _predictor, _loaded_version_dir

    resolved_dir = str(Path(version_dir) if version_dir is not None else artifacts.latest_version_dir(models_dir))

    # Fast path: already loaded and it's the version we want.
    if _predictor is not None and _loaded_version_dir == resolved_dir:
        return _predictor

    with _predictor_lock:
        # Re-check inside the lock in case another thread just finished loading.
        if _predictor is not None and _loaded_version_dir == resolved_dir:
            return _predictor

        logger.info("Loading model version from %s", resolved_dir)
        _predictor = Predictor(resolved_dir)
        _loaded_version_dir = resolved_dir
        return _predictor


def reload_predictor(version_dir: Optional[str | Path] = None, models_dir: str | Path = "models") -> Predictor:
    """
    Force a reload even if a Predictor is already cached - e.g. after
    retraining produces a new `models/vN+1/` and the running service should
    switch to it without a process restart.
    """
    global _predictor, _loaded_version_dir
    with _predictor_lock:
        _predictor = None
        _loaded_version_dir = None
    return get_predictor(version_dir=version_dir, models_dir=models_dir)


def reset_predictor() -> None:
    """
    Drop the cached Predictor (if any) without loading another one. Used by
    the admin "reset models" endpoint after model artifacts are deleted, so
    the next get_predictor() call reports a clean ArtifactNotFoundError
    instead of serving a deleted version from memory.
    """
    global _predictor, _loaded_version_dir
    with _predictor_lock:
        _predictor = None
        _loaded_version_dir = None
    logger.info("Predictor cache reset (no model loaded)")


def is_loaded() -> bool:
    """Whether a Predictor has been loaded into the singleton yet."""
    return _predictor is not None
