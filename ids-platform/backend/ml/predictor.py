"""
Singleton loader/cache for the trained inference pipeline: model, scaler,
PCA, label encoder (if present), feature names, and metadata.

Everything in backend/ml/{validator,confidence,severity,inference}.py reads
from this module rather than touching backend/ml/artifacts.py directly, so
the (relatively slow) disk load - unpickling a Random Forest, a scaler, a
fitted PCA - happens exactly once per process, no matter how many
predictions are served afterwards.

Thread-safety note: the *loading* step (get_predictor() the first time it's
called) is protected by a lock using double-checked locking, since multiple
request-handling threads could race to initialize the singleton. *Using*
an already-loaded Predictor (calling .transform()/.predict() on its cached
sklearn objects) needs no additional locking - scikit-learn's predict/
transform methods don't mutate estimator state, so concurrent reads from
multiple threads are safe.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Optional

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
    StandardScaler, IncrementalPCA, optional LabelEncoder, PCA feature
    names, and metadata.json contents.

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
        self.encoder = bundle.get("label_encoder")  # None if no encoder.pkl was saved
        self.pca_feature_names: list[str] = bundle["feature_names"]  # PC1..PCn (PCA output space)
        self.metadata: dict = bundle["metadata"]

        # The raw, pre-scaling input feature names/order the model actually
        # expects - this is what validator.py checks incoming requests
        # against, NOT `pca_feature_names` above (those describe the PCA
        # *output*, used for metadata/reporting, not input validation).
        # sklearn populates `feature_names_in_` automatically because
        # feature_engineering.fit_scaler() fits on a DataFrame.
        if hasattr(self.scaler, "feature_names_in_"):
            self.expected_features: list[str] = list(self.scaler.feature_names_in_)
        else:
            # Defensive fallback for a scaler fitted on a bare ndarray
            # (shouldn't happen via feature_engineering.py, but a hand-built
            # or older artifact shouldn't crash the whole service on load).
            logger.warning(
                "Loaded scaler has no feature_names_in_; falling back to positional "
                "feature validation only (no name-based checks possible)."
            )
            self.expected_features = []

        logger.info(
            "Predictor loaded: version=%s, model=%s, raw_features=%d, pca_components=%d, encoder=%s",
            self.version_label,
            type(self.model).__name__,
            len(self.expected_features),
            len(self.pca_feature_names),
            "present" if self.encoder is not None else "absent (model predicts labels directly)",
        )

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        """
        Scale then PCA-transform an already-validated, correctly-ordered
        feature matrix.

        Returns a DataFrame (not a bare ndarray) with columns named exactly
        `self.pca_feature_names` (PC1..PCn) - the model was trained on a
        DataFrame with those same column names (see training.py /
        feature_engineering.transform_with_pca), so preserving them here
        avoids sklearn's "X does not have valid feature names" warning and
        keeps predict-time input shaped identically to train-time input.
        """
        scaled = self.scaler.transform(X)
        pca_output = self.pca.transform(scaled)
        return pd.DataFrame(pca_output, columns=self.pca_feature_names, index=X.index)

    def decode_label(self, raw_prediction) -> str:
        """
        Translate a raw model output into a human-readable attack label.

        If a LabelEncoder was saved with this version, use it. Otherwise
        the model was trained directly on string labels (the notebook's
        approach - see artifacts.py's note on ENCODER_FILENAME), so the
        raw prediction *is* already the label.
        """
        if self.encoder is not None:
            return str(self.encoder.inverse_transform([raw_prediction])[0])
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
