"""
Singleton loader/cache for the trained inference pipeline: model only.
No PCA, no StandardScaler - the deployed model operates on raw features directly.

Everything in backend/ml/{validator,confidence,severity,inference}.py reads
from this module rather than touching backend/ml/artifacts.py directly, so
the (relatively slow) disk load - unpickling a LightGBM/Random Forest model -
happens exactly once per process, no matter how many predictions are served
afterwards.

Thread-safety note: the *loading* step (get_predictor() the first time it's
called) is protected by a lock using double-checked locking, since multiple
request-handling threads could race to initialize the singleton. *Using*
an already-loaded Predictor (calling .predict() on its cached model) needs no
additional locking - scikit-learn's predict methods don't mutate estimator
state, so concurrent reads from multiple threads are safe.
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
    Holds one fully-loaded model version in memory: the fitted model
    (LightGBM or Random Forest) and the canonical feature names.
    
    The deployed model operates directly on the canonical feature set
    (53 features) - no PCA, no StandardScaler. The model is trained on
    the canonical feature set and expects exactly those 53 features in
    the correct order.
    
    Not meant to be constructed directly - use get_predictor() to get the
    process-wide singleton instance.
    """

    def __init__(self, version_dir: str | Path):
        self.version_dir = Path(version_dir)
        self.version_label = self.version_dir.name  # e.g. "v1"

        bundle = artifacts.load_model_bundle(self.version_dir)
        self.model = bundle["model"]
        self.metadata: dict = bundle["metadata"]

        # The canonical feature names/order the model actually expects.
        # This comes from the canonical feature schema, not from the scaler.
        self.expected_features: list[str] = CANONICAL_FEATURE_NAMES
        
        # Verify the loaded model's expected features match our schema
        if hasattr(self.model, "feature_names_in_"):
            model_features = list(self.model.feature_names_in_)
            if set(model_features) != set(self.expected_features):
                logger.warning(
                    "Model feature names (%d) don't match canonical schema (%d). "
                    "Model: %s, Expected: %s",
                    len(model_features), len(self.expected_features),
                    sorted(model_features)[:5], sorted(self.expected_features)[:5]
                )

        logger.info(
            "Predictor loaded: version=%s, model=%s, features=%d",
            self.version_label,
            type(self.model).__name__,
            len(self.expected_features),
        )

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """
        Predict on raw canonical features.
        
        Args:
            X: DataFrame with exactly the canonical feature columns in order.
            
        Returns:
            Predicted class labels as numpy array.
        """
        # Validate input features
        if list(X.columns) != self.expected_features:
            missing = set(self.expected_features) - set(X.columns)
            extra = set(X.columns) - set(self.expected_features)
            if missing:
                raise ValueError(f"Missing features: {missing}")
            if extra:
                raise ValueError(f"Extra features not expected: {extra}")
            if list(X.columns) != self.expected_features:
                # Reorder columns to match expected order
                X = X[self.expected_features]
        
        # Direct prediction - no scaling, no PCA
        return self.model.predict(X)
    
    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """
        Predict class probabilities on raw canonical features.
        
        Args:
            X: DataFrame with exactly the canonical feature columns in order.
            
        Returns:
            Predicted probabilities as numpy array (n_samples, n_classes).
        """
        if list(X.columns) != self.expected_features:
            missing = set(self.expected_features) - set(X.columns)
            extra = set(X.columns) - set(self.expected_features)
            if missing:
                raise ValueError(f"Missing features: {missing}")
            if extra:
                raise ValueError(f"Extra features not expected: {extra}")
            if list(X.columns) != self.expected_features:
                X = X[self.expected_features]
        
        return self.model.predict_proba(X)

    def decode_label(self, raw_prediction) -> str:
        """
        Translate a raw model output into a human-readable attack label.
        
        Since the model is trained directly on string labels, the raw
        prediction is already the label.
        """
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
