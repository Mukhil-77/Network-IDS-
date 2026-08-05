"""
Standalone example: exercises the Milestone 3 prediction service exactly as
another service would - no FastAPI, no HTTP, just Python function calls.

If no trained model exists yet under `models/`, this script first trains a
tiny demonstration model on synthetic data (using the *real*
feature_engineering.py / training.py / artifacts.py from Milestones 1-2)
so the example is runnable standalone, without requiring the full
CIC-IDS2017 dataset on disk. To run predictions against your actual
trained model instead, just make sure `models/v*/` (from
scripts/train_pipeline.py) already exists before running this script - it
will be used automatically.

Usage:
    python -m examples.example_prediction
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from backend.ml import artifacts, feature_engineering, inference, training
from backend.ml.predictor import get_predictor
from backend.utils.logger import get_logger

logger = get_logger(__name__)

MODELS_DIR = Path("models")
EXAMPLES_DIR = Path(__file__).parent


def _train_demo_model_if_missing() -> None:
    """Train a tiny demo model so this script works even with no real dataset on hand."""
    if artifacts.list_versions(MODELS_DIR):
        logger.info("Existing model version(s) found under %s - reusing.", MODELS_DIR)
        return

    logger.info("No trained model found under %s - training a small demo model first.", MODELS_DIR)
    rng = np.random.default_rng(0)
    n = 800
    columns = [
        "Flow Duration",
        "Total Fwd Packets",
        "Total Backward Packets",
        "Flow Bytes/s",
        "Flow Packets/s",
        "Fwd Packet Length Mean",
        "Bwd Packet Length Mean",
        "Packet Length Std",
    ]
    data = {col: rng.normal(loc=100, scale=25, size=n) for col in columns}
    df = pd.DataFrame(data)
    is_attack = df["Flow Packets/s"] > df["Flow Packets/s"].median()
    df["Attack Type"] = np.where(is_attack, "DoS", "BENIGN")

    X, y = feature_engineering.split_features_and_target(df)
    fe = feature_engineering.FeatureEngineer.fit(X, batch_size=100)
    pca_df = fe.transform_to_frame(X, target=y)

    dataset = training.prepare_multiclass_dataset(pca_df, min_class_count=10, cap_threshold=1000, cap_per_class=1000)
    trained = training.train_random_forest_models(
        dataset, param_sets=[{"n_estimators": 20, "max_depth": 6, "random_state": 0}]
    )[0]

    version_dir = artifacts.next_version_dir(MODELS_DIR)
    metadata = artifacts.build_metadata(
        model_name=trained.name,
        dataset="synthetic-demo",
        accuracy=1.0,
        precision=1.0,
        recall=1.0,
        f1_score=1.0,
        features=fe.feature_names,
        pca_components=len(fe.feature_names),
    )
    artifacts.save_model_bundle(
        version_dir=version_dir,
        model=trained.model,
        scaler=fe.scaler,
        pca=fe.pca,
        feature_names=fe.feature_names,
        metadata=metadata,
    )
    logger.info("Demo model trained and saved to %s", version_dir)


def main() -> None:
    _train_demo_model_if_missing()

    predictor = get_predictor(models_dir=MODELS_DIR)
    logger.info("Loaded model version %s (%s)", predictor.version_label, type(predictor.model).__name__)

    example_input_path = EXAMPLES_DIR / "example_input.json"
    if example_input_path.is_file():
        request_payload = json.loads(example_input_path.read_text())["features"]
    else:
        # Build a request from the loaded model's actual expected features,
        # since a hardcoded example_input.json wouldn't necessarily match a
        # freshly-trained demo model's real column names.
        request_payload = {name: 120.0 for name in predictor.expected_features}

    print("Request:")
    print(json.dumps({"features": request_payload}, indent=2))

    try:
        response = inference.predict(request_payload, predictor=predictor)
    except inference.FeatureValidationFailed as exc:
        print("\nValidation failed:")
        for error in exc.errors:
            print(f"  [{error.error_type}] {error.field}: {error.message}")
        return
    except inference.InferencePipelineError as exc:
        print(f"\nInference pipeline error: {exc}")
        return

    print("\nResponse:")
    print(response.model_dump_json(indent=2))

    (EXAMPLES_DIR / "example_output.json").write_text(response.model_dump_json(indent=2))
    (EXAMPLES_DIR / "example_input.json").write_text(json.dumps({"features": request_payload}, indent=2))


if __name__ == "__main__":
    main()
