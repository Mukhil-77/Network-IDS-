"""
Training module for API compatibility.

This module provides the training functions that backend/services/prediction_service.py
expects, using the new v2 training script.
"""

import sys
from pathlib import Path

# Algorithm families available for training via API
AVAILABLE_FAMILIES = ["lightgbm"]

# Special value meaning "train all families"
ALL_ALGORITHMS = "all"


def available_families() -> list[str]:
    """Return list of algorithm families available for training."""
    return AVAILABLE_FAMILIES.copy()


class TrainingCancelled(Exception):
    """Raised when background training is cancelled by operator."""
    pass


def run_family(
    data_path: str,
    algorithm: str,
    models_dir: str,
    should_stop=None,
) -> list[dict]:
    """
    Run training for a specific algorithm family.
    
    This is called by prediction_service.train_model() in a background thread.
    
    Args:
        data_path: Path to training data
        algorithm: Algorithm family name (e.g., "lightgbm")
        models_dir: Directory to save model versions
        should_stop: Optional callable that returns True if training should stop
    
    Returns:
        List of dicts with training results (version_dir, accuracy, etc.)
    """
    if algorithm not in AVAILABLE_FAMILIES and algorithm != ALL_ALGORITHMS:
        raise ValueError(f"Unknown algorithm family: {algorithm}")
    
    # Import and run the v2 training script
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from backend.scripts.train_v1_model import train_model
    
    # Check for cancellation before starting
    if should_stop and should_stop():
        raise TrainingCancelled()
    
    # Run training (this will create a new version directory via next_version_dir)
    metadata = train_model()
    
    # Check for cancellation after training
    if should_stop and should_stop():
        raise TrainingCancelled()
    
    # Return result in expected format
    # Find the version directory that was just created
    from backend.ml.artifacts import list_versions, _resolve_models_root
    versions = list_versions(models_dir)
    if versions:
        latest_version = versions[-1]
        version_dir = str(_resolve_models_root(models_dir) / f"v{latest_version}")
    else:
        version_dir = str(_resolve_models_root(models_dir) / "v1")
    
    return [{
        "version_dir": version_dir,
        "accuracy": metadata.get("accuracy"),
        "model_name": metadata.get("model_name"),
        "dataset": metadata.get("dataset"),
    }]


def run_all(
    data_path: str,
    models_dir: str,
    should_stop=None,
) -> list[dict]:
    """Run training for all algorithm families sequentially."""
    results = []
    for family in AVAILABLE_FAMILIES:
        if should_stop and should_stop():
            raise TrainingCancelled()
        family_results = run_family(data_path, family, models_dir, should_stop)
        results.extend(family_results)
    return results