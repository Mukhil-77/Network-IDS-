"""
End-to-end training entry point: raw CSVs -> preprocessing -> feature
engineering -> model training -> evaluation -> versioned artifacts.

This is glue code only - every step it calls already exists in
backend.ml.{preprocessing,feature_engineering,training,evaluation,artifacts}.
Nothing here contains modeling logic of its own.

Usage:
    python -m scripts.train_pipeline /path/to/raw/csv/dir

    # Optional: choose where models/ is created (defaults to ./models)
    python -m scripts.train_pipeline /path/to/raw/csv/dir --models-dir ./models
"""

from __future__ import annotations

import argparse

from backend.ml import artifacts, evaluation, feature_engineering, preprocessing, training
from backend.ml.constants import BEST_MODEL_VARIANT_INDEX, TARGET_COLUMN
from backend.utils.logger import get_logger

logger = get_logger(__name__)


def run(data_dir: str, models_dir: str = "models") -> None:
    # 1. Preprocessing (Milestone 1 - unchanged)
    df = preprocessing.preprocess_dataset(data_dir)

    # 2. Feature engineering: fit scaler + PCA once, on the full cleaned dataset
    X, y = feature_engineering.split_features_and_target(df, target_column=TARGET_COLUMN)
    fe = feature_engineering.FeatureEngineer.fit(X)
    pca_df = fe.transform_to_frame(X, target=y, target_column=TARGET_COLUMN)

    # 3. Binary models (LogisticRegression x2, SVM x2)
    binary_dataset = training.prepare_binary_dataset(pca_df, target_column=TARGET_COLUMN)
    binary_models = training.train_all_binary_models(binary_dataset)
    binary_results = [
        evaluation.evaluate_model(tm.name, tm.model, binary_dataset.X_test, binary_dataset.y_test, tm.cv_scores)
        for tm in binary_models
    ]
    logger.info("Binary model comparison: %s", evaluation.compare_models(binary_results))

    # 4. Multi-class models (RandomForest x2, DecisionTree x2, KNN x2)
    multiclass_dataset = training.prepare_multiclass_dataset(pca_df, target_column=TARGET_COLUMN)
    rf_models = training.train_random_forest_models(multiclass_dataset)
    other_multiclass_models = training.train_decision_tree_models(
        multiclass_dataset
    ) + training.train_knn_models(multiclass_dataset)

    multiclass_results = [
        evaluation.evaluate_model(tm.name, tm.model, multiclass_dataset.X_test, multiclass_dataset.y_test, tm.cv_scores)
        for tm in rf_models + other_multiclass_models
    ]
    logger.info("Multi-class model comparison: %s", evaluation.compare_models(multiclass_results))

    # 5. Persist the best-performing model (Random Forest Model 2, per the
    #    notebook's own conclusion - see constants.BEST_MODEL_VARIANT_INDEX).
    best_model = rf_models[BEST_MODEL_VARIANT_INDEX]
    best_result = next(r for r in multiclass_results if r.model_name == best_model.name)

    version_dir = artifacts.next_version_dir(models_dir)
    metadata = artifacts.build_metadata(
        model_name=best_model.name,
        dataset="CIC-IDS2017",
        accuracy=best_result.accuracy,
        precision=best_result.precision_macro,
        recall=best_result.recall_macro,
        f1_score=best_result.f1_macro,
        features=fe.feature_names,
        pca_components=len(fe.feature_names),
    )
    artifacts.save_model_bundle(
        version_dir=version_dir,
        model=best_model.model,
        scaler=fe.scaler,
        pca=fe.pca,
        feature_names=fe.feature_names,
        metadata=metadata,
    )
    logger.info("Training complete. Best model '%s' saved to %s", best_model.name, version_dir)


def main() -> None:
    parser = argparse.ArgumentParser(description="Train and version the IDS ML pipeline")
    parser.add_argument("data_dir", help="Directory containing the raw CIC-IDS2017 CSV files")
    parser.add_argument("--models-dir", default="models", help="Root directory for versioned model output")
    args = parser.parse_args()

    run(args.data_dir, args.models_dir)


if __name__ == "__main__":
    main()
