"""
Singleton loader/cache for the trained inference pipeline: model + scaler + (optional PCA).

The v1 model operates on MinMaxScaler-transformed features with no PCA.
Pipeline: Raw features -> Categorical Encoding -> Imputer -> MinMaxScaler -> RandomForest

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
from typing import Optional, Any

import numpy as np
import pandas as pd

from backend.ml import artifacts
from backend.ml.schemas import ModelMetadata
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class ModelNotLoadedError(RuntimeError):
    """Raised when inference is attempted before a model has been successfully loaded."""


class Predictor:
    """
    Holds one fully-loaded model version in memory: the fitted model,
    scaler, optional PCA, imputer, categorical encoders, and the raw
    feature names the scaler expects.

    The pipeline can be:
        Raw features -> Categorical Encoding -> Imputer -> Scaler -> PCA (optional) -> Model
    
    Not meant to be constructed directly - use get_predictor() to get the
    process-wide singleton instance.
    """

    def __init__(self, version_dir: str | Path):
        self.version_dir = Path(version_dir)
        self.version_label = self.version_dir.name  # e.g. "v1"

        bundle = artifacts.load_model_bundle(self.version_dir)
        self.model = bundle["model"]
        self.scaler = bundle["scaler"]
        self.pca = bundle.get("pca")
        self.metadata: dict = bundle["metadata"]
        self.imputer = bundle.get("imputer")
        self.cat_encoders = bundle.get("cat_encoders", {})

        # The raw feature names the scaler expects (from the training data)
        if hasattr(self.scaler, "feature_names_in_"):
            self.raw_feature_names: list[str] = list(self.scaler.feature_names_in_)
        else:
            # Fallback: use the feature_names.json from the bundle
            self.raw_feature_names = bundle.get("feature_names", [])

        # PCA component names (PC1, PC2, ...) - only if PCA exists
        if self.pca is not None:
            self.pca_components = self.metadata.get("pca_components", self.pca.n_components_)
            self.pca_feature_names = [f"PC{i+1}" for i in range(self.pca_components)]
        else:
            self.pca_components = 0
            self.pca_feature_names = []

        # Detect whether this model uses PCA or works directly on scaled features
        self._uses_pca = self.pca is not None
        logger.info(
            "Predictor loaded: version=%s, model=%s, raw_features=%d, pca_components=%d, uses_pca=%s, has_imputer=%s, has_cat_encoders=%s",
            self.version_label,
            type(self.model).__name__,
            len(self.raw_feature_names),
            self.pca_components,
            self._uses_pca,
            self.imputer is not None,
            bool(self.cat_encoders),
        )

    def _is_lightgbm(self) -> bool:
        """Check if the model is a LightGBM Booster."""
        return type(self.model).__name__ == 'Booster'

    def _is_sklearn_ensemble(self) -> bool:
        """Check if model is an sklearn ensemble (RandomForest, etc.)."""
        return hasattr(self.model, 'predict_proba') and hasattr(self.model, 'n_features_in_')

    def _encode_categorical(self, X: pd.DataFrame) -> pd.DataFrame:
        """Apply categorical encoders to the input features."""
        X = X.copy()
        for col, encoder in self.cat_encoders.items():
            if col in X.columns:
                # Handle unseen categories
                X[col] = X[col].astype(str)
                unknown_mask = ~X[col].isin(encoder.label_encoder.classes_)
                X.loc[unknown_mask, col] = 'Unknown'
                X[col] = encoder.label_encoder.transform(X[col])
        return X

    def _transform(self, X: pd.DataFrame) -> np.ndarray:
        """
        Apply the full preprocessing pipeline: categorical encoding -> imputer -> scaler -> PCA (if needed).
        
        Args:
            X: DataFrame with raw feature columns matching scaler's expected input.
            
        Returns:
            Transformed array ready for the model (scaled, or scaled+PCA).
        """
        # Ensure columns match expected input
        if list(X.columns) != self.raw_feature_names:
            missing = set(self.raw_feature_names) - set(X.columns)
            extra = set(X.columns) - set(self.raw_feature_names)
            if missing:
                raise ValueError(f"Missing raw features for scaler: {missing}")
            if extra:
                raise ValueError(f"Extra raw features not expected by scaler: {extra}")
            if list(X.columns) != self.raw_feature_names:
                X = X[self.raw_feature_names]

        # 1. Categorical encoding
        if self.cat_encoders:
            X = self._encode_categorical(X)

        # 2. Imputer
        if self.imputer is not None:
            X = pd.DataFrame(self.imputer.transform(X), columns=X.columns, index=X.index)

        # 3. Apply scaler
        X_scaled = self.scaler.transform(X)

        # 4. Apply PCA only if model expects it
        if self._uses_pca and self.pca is not None:
            X_pca = self.pca.transform(X_scaled)
            return X_pca
        else:
            return X_scaled

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """
        Predict on raw features by applying the full pipeline.
        
        Args:
            X: DataFrame with exactly the raw feature columns the scaler expects.
            
        Returns:
            Predicted class labels as numpy array.
        """
        X_transformed = self._transform(X)

        if self._is_lightgbm():
            # LightGBM Booster.predict() returns probabilities, need argmax for labels
            probas = self.model.predict(X_transformed)
            return np.argmax(probas, axis=1)
        else:
            preds = self.model.predict(X_transformed)
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
        X_transformed = self._transform(X)

        if self._is_lightgbm():
            # LightGBM Booster.predict() returns probabilities directly
            return self.model.predict(X_transformed)
        elif hasattr(self.model, 'predict_proba'):
            return self.model.predict_proba(X_transformed)
        else:
            # Fallback: return uniform probabilities
            n_samples = X_transformed.shape[0]
            n_classes = len(self.metadata.get('classes', [1, 2]))
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

        # Handle sklearn LabelEncoder case
        if hasattr(self, 'label_encoder') and self.label_encoder is not None:
            try:
                return self.label_encoder.inverse_transform([int(raw_prediction)])[0]
            except Exception:
                pass

        # Handle metadata label mapping
        label_mapping = self.metadata.get('label_mapping', {})
        if label_mapping:
            key = int(raw_prediction)
            if key in label_mapping:
                return label_mapping[key]
            if str(key) in label_mapping:
                return label_mapping[str(key)]

        # For v1 multi-class: classes are stored in metadata['classes']
        classes = self.metadata.get('classes', [])
        if classes:
            idx = int(raw_prediction)
            if 0 <= idx < len(classes):
                return classes[idx]

        return str(raw_prediction)

    def get_severity(self, attack_label: str) -> str:
        """Get severity level for an attack label."""
        severity_mapping = self.metadata.get('severity_mapping', {})
        return severity_mapping.get(attack_label, 'MEDIUM')

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