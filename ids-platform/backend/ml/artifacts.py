"""
Versioned persistence for every trained-pipeline artifact: the model,
the fitted StandardScaler and IncrementalPCA, the LabelEncoder, the PCA
feature names, and a metadata.json describing how the version was produced.

Nothing in this module trains or transforms anything - it is pure I/O. That
split exists so feature_engineering.py and training.py stay testable with
plain in-memory objects, while this module owns the one place that knows
about file paths, filenames, and on-disk layout:

    models/
        v1/
            rf_model.pkl
            scaler.pkl
            pca.pkl
            label_encoder.pkl
            feature_names.json
            metadata.json
        v2/
            ...

Every training run gets a new version directory (see next_version_dir());
nothing is ever overwritten in place, so a bad retrain never destroys the
model currently serving predictions and rollback is just "point the API at
the previous version directory".
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final, Optional

import joblib
import sklearn
from sklearn.decomposition import IncrementalPCA
from sklearn.preprocessing import LabelEncoder, StandardScaler

from backend.ml.constants import PROJECT_VERSION
from backend.utils.logger import get_logger

logger = get_logger(__name__)

# --------------------------------------------------------------------------
# On-disk filenames - single source of truth so no other module hardcodes
# a string like "scaler.pkl" and risks drifting from what's actually saved.
# --------------------------------------------------------------------------
MODEL_FILENAME: Final[str] = "rf_model.pkl"
SCALER_FILENAME: Final[str] = "scaler.pkl"
PCA_FILENAME = "pca.pkl"
ENCODER_FILENAME = "label_encoder.pkl"
FEATURE_NAMES_FILENAME = "feature_names.json"
METADATA_FILENAME = "metadata.json"

DEFAULT_MODELS_DIR = "models"


class ArtifactNotFoundError(FileNotFoundError):
    """Raised when a requested artifact file doesn't exist in a version directory."""


# --------------------------------------------------------------------------
# Version directory management
# --------------------------------------------------------------------------

def _resolve_models_root(base_dir: Optional[str | Path] = None) -> Path:
    return Path(base_dir) if base_dir is not None else Path(DEFAULT_MODELS_DIR)


def list_versions(base_dir: Optional[str | Path] = None) -> list[int]:
    """Return all existing model version numbers (from `models/vN/` dirs), sorted ascending."""
    root = _resolve_models_root(base_dir)
    if not root.is_dir():
        return []

    versions = []
    for entry in root.iterdir():
        if entry.is_dir() and entry.name.startswith("v") and entry.name[1:].isdigit():
            versions.append(int(entry.name[1:]))
    return sorted(versions)


def latest_version_dir(base_dir: Optional[str | Path] = None) -> Path:
    """
    Return the directory of the highest existing model version.

    Raises:
        ArtifactNotFoundError: If no versioned model directory exists yet.
    """
    versions = list_versions(base_dir)
    if not versions:
        root = _resolve_models_root(base_dir)
        raise ArtifactNotFoundError(f"No model versions found under '{root}'")

    return _resolve_models_root(base_dir) / f"v{versions[-1]}"


def next_version_dir(base_dir: Optional[str | Path] = None) -> Path:
    """
    Compute (and create) the directory for the *next* model version, e.g.
    if v1 and v2 exist, returns and creates `models/v3/`.
    """
    versions = list_versions(base_dir)
    next_num = (versions[-1] + 1) if versions else 1
    version_dir = _resolve_models_root(base_dir) / f"v{next_num}"
    version_dir.mkdir(parents=True, exist_ok=False)
    logger.info("Created new model version directory: %s", version_dir)
    return version_dir


# --------------------------------------------------------------------------
# Model (rf_model.pkl)
# --------------------------------------------------------------------------

def save_model(model: Any, version_dir: str | Path, filename: str = MODEL_FILENAME) -> Path:
    """Save a trained model (any fitted sklearn estimator) to `version_dir/filename`."""
    path = Path(version_dir) / filename
    joblib.dump(model, path)
    logger.info("Saved model -> %s", path)
    return path


def load_model(version_dir: str | Path, filename: str = MODEL_FILENAME) -> Any:
    """Load a trained model from `version_dir/filename`."""
    path = Path(version_dir) / filename
    if not path.is_file():
        raise ArtifactNotFoundError(f"Model file not found: {path}")
    return joblib.load(path)


# --------------------------------------------------------------------------
# StandardScaler (scaler.pkl)
# --------------------------------------------------------------------------

def save_scaler(scaler: StandardScaler, version_dir: str | Path) -> Path:
    path = Path(version_dir) / SCALER_FILENAME
    joblib.dump(scaler, path)
    logger.info("Saved scaler -> %s", path)
    return path


def load_scaler(version_dir: str | Path) -> StandardScaler:
    path = Path(version_dir) / SCALER_FILENAME
    if not path.is_file():
        raise ArtifactNotFoundError(f"Scaler file not found: {path}")
    return joblib.load(path)


# --------------------------------------------------------------------------
# IncrementalPCA (pca.pkl)
# --------------------------------------------------------------------------

def save_pca(pca: IncrementalPCA, version_dir: str | Path) -> Path:
    path = Path(version_dir) / PCA_FILENAME
    joblib.dump(pca, path)
    logger.info("Saved PCA -> %s", path)
    return path


def load_pca(version_dir: str | Path) -> IncrementalPCA:
    path = Path(version_dir) / PCA_FILENAME
    if not path.is_file():
        raise ArtifactNotFoundError(f"PCA file not found: {path}")
    return joblib.load(path)


# --------------------------------------------------------------------------
# LabelEncoder (label_encoder.pkl)
#
# The notebook's multi-class models were trained directly on string labels
# ("DDoS", "Port Scan", ...) rather than an explicit LabelEncoder, so
# training.py doesn't need one to reproduce notebook behavior. It's
# supported here anyway (as the Milestone 2 spec requires) because a
# production API returning a bare string is fragile compared to returning
# a stable encoded class id + a decode step; training.py can adopt it in a
# later milestone without any change to this module.
# --------------------------------------------------------------------------

def save_encoder(encoder: LabelEncoder, version_dir: str | Path) -> Path:
    path = Path(version_dir) / ENCODER_FILENAME
    joblib.dump(encoder, path)
    logger.info("Saved label encoder -> %s", path)
    return path


def load_encoder(version_dir: str | Path) -> LabelEncoder:
    path = Path(version_dir) / ENCODER_FILENAME
    if not path.is_file():
        raise ArtifactNotFoundError(f"Label encoder file not found: {path}")
    return joblib.load(path)


# --------------------------------------------------------------------------
# feature_names.json
# --------------------------------------------------------------------------

def save_feature_names(feature_names: list[str], version_dir: str | Path) -> Path:
    path = Path(version_dir) / FEATURE_NAMES_FILENAME
    path.write_text(json.dumps(feature_names, indent=2))
    logger.info("Saved %d feature name(s) -> %s", len(feature_names), path)
    return path


def load_feature_names(version_dir: str | Path) -> list[str]:
    path = Path(version_dir) / FEATURE_NAMES_FILENAME
    if not path.is_file():
        raise ArtifactNotFoundError(f"Feature names file not found: {path}")
    return json.loads(path.read_text())


# --------------------------------------------------------------------------
# metadata.json
# --------------------------------------------------------------------------

def build_metadata(
    model_name: str,
    dataset: str,
    accuracy: float,
    precision: float,
    recall: float,
    f1_score: float,
    features: list[str],
    pca_components: int,
    training_date: Optional[str] = None,
) -> dict:
    """
    Build a metadata dict matching the required schema:

        {
          "model_name": "", "dataset": "", "training_date": "",
          "accuracy": "", "precision": "", "recall": "", "f1_score": "",
          "features": [], "pca_components": "",
          "sklearn_version": "", "project_version": ""
        }

    `sklearn_version` and `project_version` are filled in automatically
    (the installed sklearn version, and constants.PROJECT_VERSION) so every
    trained model is traceable to the exact library version and codebase
    contract that produced it.
    """
    return {
        "model_name": model_name,
        "dataset": dataset,
        "training_date": training_date or datetime.now(timezone.utc).isoformat(),
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1_score": f1_score,
        "features": features,
        "pca_components": pca_components,
        "sklearn_version": sklearn.__version__,
        "project_version": PROJECT_VERSION,
    }


def save_metadata(metadata: dict, version_dir: str | Path) -> Path:
    path = Path(version_dir) / METADATA_FILENAME
    path.write_text(json.dumps(metadata, indent=2, default=str))
    logger.info("Saved metadata -> %s", path)
    return path


def load_metadata(version_dir: str | Path) -> dict:
    path = Path(version_dir) / METADATA_FILENAME
    if not path.is_file():
        raise ArtifactNotFoundError(f"Metadata file not found: {path}")
    return json.loads(path.read_text())


# --------------------------------------------------------------------------
# Convenience: save/load everything for one model version in one call
# --------------------------------------------------------------------------

def save_model_bundle(
    version_dir: str | Path,
    model: Any,
    scaler: StandardScaler,
    pca: IncrementalPCA,
    feature_names: list[str],
    metadata: dict,
    encoder: Optional[LabelEncoder] = None,
) -> None:
    """Save every artifact for a trained pipeline version in one call."""
    save_model(model, version_dir)
    save_scaler(scaler, version_dir)
    save_pca(pca, version_dir)
    save_feature_names(feature_names, version_dir)
    save_metadata(metadata, version_dir)
    if encoder is not None:
        save_encoder(encoder, version_dir)
    logger.info("Saved full model bundle -> %s", version_dir)


def load_model_bundle(version_dir: str | Path) -> dict:
    """
    Load every artifact for a model version in one call. `label_encoder` is
    omitted from the result if no encoder.pkl exists for that version.
    """
    bundle = {
        "model": load_model(version_dir),
        "scaler": load_scaler(version_dir),
        "pca": load_pca(version_dir),
        "feature_names": load_feature_names(version_dir),
        "metadata": load_metadata(version_dir),
    }
    encoder_path = Path(version_dir) / ENCODER_FILENAME
    if encoder_path.is_file():
        bundle["label_encoder"] = load_encoder(version_dir)
    return bundle
