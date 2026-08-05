"""
Batch training: train every model variant and persist each as its own
versioned artifact bundle under models/v1, models/v2, ...

Each training run calls the same building blocks the single-run pipeline
(scripts/train_pipeline.py) uses - preprocessing -> feature engineering
(scaler + IncrementalPCA) -> training -> evaluation - but instead of keeping
only the single best model it saves *every* variant, so the API's
POST /model/switch/{version} can switch between real, comparable artifacts.

Artifacts are never overwritten: every model is written to a brand-new
version directory (artifacts.next_version_dir()), exactly as documented in
the original setup's model-persistence rules.

Usage:
    python -m backend.ml.train_all_models /path/to/raw/csv/dir
    python -m backend.ml.train_all_models /path/to/raw/csv/dir --models-dir ./models
"""

from __future__ import annotations

import argparse

from backend.ml import artifacts, evaluation, feature_engineering, preprocessing, training
from backend.ml.constants import TARGET_COLUMN
from backend.utils.logger import get_logger

logger = get_logger(__name__)


def run(data_dir: str, models_dir: str = "models", *, save_all: bool = True) -> list[dict]:
    """Train all binary + multi-class variants and persist them as versioned bundles."""
    # 1. Preprocessing (Milestone 1 - unchanged)
    df = preprocessing.preprocess_dataset(data_dir)

    # 2. Feature engineering: fit scaler + PCA once, on the full cleaned dataset
    X, y = feature_engineering.split_features_and_target(df, target_column=TARGET_COLUMN)
    fe = feature_engineering.FeatureEngineer.fit(X)
    pca_df = fe.transform_to_frame(X, target=y, target_column=TARGET_COLUMN)

    saved: list[dict] = []

    def _save(model: training.TrainedModel, result: evaluation.EvaluationResult) -> dict:
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
        saved.append(entry)
        logger.info("Saved '%s' to %s (accuracy=%.4f)", model.name, version_dir, result.accuracy)
        return entry

    # 3. Binary models (LogisticRegression x2, SVM x2)
    binary_dataset = training.prepare_binary_dataset(pca_df, target_column=TARGET_COLUMN)
    binary_models = training.train_all_binary_models(binary_dataset)
    binary_results = [
        evaluation.evaluate_model(tm.name, tm.model, binary_dataset.X_test, binary_dataset.y_test, tm.cv_scores)
        for tm in binary_models
    ]
    logger.info("Binary model comparison: %s", evaluation.compare_models(binary_results))
    if save_all:
        for model, result in zip(binary_models, binary_results):
            _save(model, result)

    # 4. Multi-class models (RandomForest x2, DecisionTree x2, KNN x2)
    multiclass_dataset = training.prepare_multiclass_dataset(pca_df, target_column=TARGET_COLUMN)
    multiclass_models = training.train_all_multiclass_models(multiclass_dataset)
    multiclass_results = [
        evaluation.evaluate_model(tm.name, tm.model, multiclass_dataset.X_test, multiclass_dataset.y_test, tm.cv_scores)
        for tm in multiclass_models
    ]
    logger.info("Multi-class model comparison: %s", evaluation.compare_models(multiclass_results))
    if save_all:
        for model, result in zip(multiclass_models, multiclass_results):
            _save(model, result)

    return saved


def main() -> None:
    parser = argparse.ArgumentParser(description="Train all model variants and save each as a versioned artifact")
    parser.add_argument("data_dir", help="Directory containing the raw CIC-IDS2017 CSV files")
    parser.add_argument("--models-dir", default="models", help="Root directory for versioned model output")
    args = parser.parse_args()

    saved = run(args.data_dir, args.models_dir)
    logger.info("Training complete: %d model(s) saved under %s", len(saved), args.models_dir)


if __name__ == "__main__":
    main()
