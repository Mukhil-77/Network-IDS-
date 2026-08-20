"""
Train a single algorithm family (as opposed to train_all_models.py's every
variant) and persist each trained variant as its own versioned artifact
bundle under models/vN.

Backs the API's POST /model/train so an operator can train one family at a
time from the dashboard instead of running the whole batch pipeline.

Reuses the exact same building blocks as train_all_models.py - preprocessing
-> feature engineering (scaler + IncrementalPCA) -> family trainer ->
evaluation -> artifacts.save_model_bundle - so results are directly
comparable with batch-trained versions.

Usage:
    python -m backend.ml.train_one random_forest
    python -m backend.ml.train_one svm --data-dir /path/to/csv --models-dir ./models
"""

from __future__ import annotations

import argparse
from typing import Callable, Optional

from backend.ml.constants import TARGET_COLUMN
from backend.ml.evaluation import EvaluationResult, evaluate_model
from backend.ml.training import (
    Dataset,
    TrainedModel,
    prepare_binary_dataset,
    prepare_multiclass_dataset,
    train_decision_tree_models,
    train_knn_models,
    train_logistic_regression_models,
    train_random_forest_models,
    train_svm_models,
)
from backend.utils.logger import get_logger

logger = get_logger(__name__)

# Algorithm family -> (dataset kind, [trainers]). Binary trainers run on the
# balanced BENIGN-vs-attack dataset, multi-class trainers on the attack-class
# one - same split train_all_models.py makes.
FAMILIES: dict[str, tuple[str, list[object]]] = {
    "logistic_regression": ("binary", [train_logistic_regression_models]),
    "svm": ("binary", [train_svm_models]),
    "random_forest": ("multiclass", [train_random_forest_models]),
    "decision_tree": ("multiclass", [train_decision_tree_models]),
    "knn": ("multiclass", [train_knn_models]),
}

ALGORITHM_CHOICES = sorted(FAMILIES)

# Special value POST /model/train accepts to run every family back-to-back
# in one background job (cancellable between families like any other run).
ALL_ALGORITHMS = "all"


def available_families() -> list[str]:
    """The algorithm families POST /model/train accepts."""
    return list(ALGORITHM_CHOICES)


class TrainingCancelled(RuntimeError):
    """Raised mid-run when an operator asks the background training to stop."""


def _check_cancelled(should_stop: Optional[Callable[[], bool]]) -> None:
    """Cooperate with an operator-requested stop between heavy work units."""
    if should_stop is not None and should_stop():
        raise TrainingCancelled("Training cancelled by operator")


def run_family(
    data_dir: str,
    family: str,
    models_dir: str = "models",
    should_stop: Optional[Callable[[], bool]] = None,
) -> list[dict]:
    """
    Train every variant in one family and save each as a versioned bundle.

    Returns entries shaped like train_all_models.run's:
    {"version_dir", "name", "accuracy", ... (metadata)}.

    When `should_stop` (a callable returning True when the operator wants to
    abort) is provided, it is polled between discrete work steps, and a
    TrainingCancelled is raised so the caller can mark the run as stopped.
    Variants already saved before the stop stay on disk.

    Raises ValueError for an unknown family; TrainingCancelled on abort.
    """
    if family not in FAMILIES:
        raise ValueError(
            f"Unknown algorithm family '{family}'. Valid choices: {ALGORITHM_CHOICES}"
        )

    # Lazy imports: the training stack pulls in sklearn/imblearn/pandas, which
    # is heavy and unnecessary at API startup - only when someone actually
    # trains from the UI.
    from backend.ml import artifacts, feature_engineering, preprocessing

    dataset_kind, trainers = FAMILIES[family]

    logger.info("Training family '%s' from data dir %s", family, data_dir)
    _check_cancelled(should_stop)
    df = preprocessing.preprocess_dataset(data_dir)
    X, y = feature_engineering.split_features_and_target(df, target_column=TARGET_COLUMN)
    fe = feature_engineering.FeatureEngineer.fit(X)
    pca_df = fe.transform_to_frame(X, target=y, target_column=TARGET_COLUMN)

    if dataset_kind == "binary":
        dataset = prepare_binary_dataset(pca_df, target_column=TARGET_COLUMN)
    else:
        dataset = prepare_multiclass_dataset(pca_df, target_column=TARGET_COLUMN)

    saved: list[dict] = []
    for trainer in trainers:
        _check_cancelled(should_stop)
        models = trainer(dataset)
        for model, result in _as_models(models, dataset):
            entry = _save(model, result, fe, models_dir)
            saved.append(entry)

    logger.info("Family '%s' produced %d model(s)", family, len(saved))
    return saved


def run_all(
    data_dir: str,
    models_dir: str = "models",
    should_stop: Optional[Callable[[], bool]] = None,
) -> list[dict]:
    """
    Train every algorithm family back-to-back, reusing run_family for each.

    The operator can stop between families (and between variants within a
    family) via `should_stop`, in which case TrainingCancelled is raised and
    everything saved so far stays on disk.
    """
    saved: list[dict] = []
    for family in ALGORITHM_CHOICES:
        _check_cancelled(should_stop)
        saved.extend(run_family(data_dir, family, models_dir, should_stop=should_stop))
    return saved


def _as_models(models: list[TrainedModel], dataset: Dataset) -> list[tuple[TrainedModel, EvaluationResult]]:
    """Evaluate each trained variant on its held-out test split."""
    return [
        (model, evaluate_model(model.name, model.model, dataset.X_test, dataset.y_test, model.cv_scores))
        for model in models
    ]


def _save(
    model: TrainedModel,
    result: EvaluationResult,
    fe: object,
    models_dir: str,
) -> dict:
    from backend.ml import artifacts

    version_dir = artifacts.next_version_dir(models_dir)
    metadata = artifacts.build_metadata(
        model_name=model.name,
        dataset="CIC-IDS2017",
        accuracy=result.accuracy,
        precision=result.precision_macro,
        recall=result.recall_macro,
        f1_score=result.f1_macro,
        features=fe.feature_names,
        pca_components=len(fe.feature_names),
    )
    artifacts.save_model_bundle(
        version_dir=version_dir,
        model=model.model,
        scaler=fe.scaler,
        pca=fe.pca,
        feature_names=fe.feature_names,
        metadata=metadata,
    )
    entry = {"version_dir": str(version_dir), "name": model.name, **metadata}
    logger.info("Saved '%s' to %s (accuracy=%.4f)", model.name, version_dir, result.accuracy)
    return entry


def main() -> None:
    parser = argparse.ArgumentParser(description="Train one algorithm family and save variants as versioned artifacts")
    parser.add_argument("family", choices=ALGORITHM_CHOICES, help="Algorithm family to train")
    parser.add_argument("--data-dir", default="data/raw", help="Directory of raw CIC-IDS2017 CSV files")
    parser.add_argument("--models-dir", default="models", help="Root directory for versioned model output")
    args = parser.parse_args()

    saved = run_family(args.data_dir, args.family, args.models_dir)
    logger.info("Training complete: %d model(s) saved under %s", len(saved), args.models_dir)


if __name__ == "__main__":
    main()