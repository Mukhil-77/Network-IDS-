"""
Shared fixtures for the Milestone 3 (prediction service) test suite.

`trained_model_dir` builds a small but *real* scaler -> PCA -> RandomForest
pipeline on synthetic data and saves it via artifacts.save_model_bundle(),
so predictor.py / inference.py tests exercise the actual save/load/predict
path rather than mocks.
"""

import numpy as np
import pandas as pd
import pytest

from backend.ml import artifacts, feature_engineering, training

RAW_FEATURE_COLUMNS = [f"Feature {i}" for i in range(8)]


@pytest.fixture
def synthetic_raw_dataframe() -> pd.DataFrame:
    """A small labeled dataset shaped like preprocessing.py's output: raw feature columns + 'Attack Type'."""
    rng = np.random.default_rng(42)
    n = 600
    data = {col: rng.normal(size=n) for col in RAW_FEATURE_COLUMNS}
    df = pd.DataFrame(data)
    # Make BENIGN separable from attacks so the trained model has a
    # meaningful (non-random) decision boundary for tests to exercise.
    is_attack = df["Feature 0"] > 0
    df["Attack Type"] = np.where(is_attack, "DoS", "BENIGN")
    return df


@pytest.fixture
def trained_model_dir(tmp_path, synthetic_raw_dataframe):
    """
    Fit a real scaler+PCA+RandomForest on synthetic_raw_dataframe and save
    it as a versioned model bundle. Returns the version directory Predictor
    should load.
    """
    df = synthetic_raw_dataframe
    X, y = feature_engineering.split_features_and_target(df)

    fe = feature_engineering.FeatureEngineer.fit(X, batch_size=100)
    pca_df = fe.transform_to_frame(X, target=y)

    dataset = training.prepare_multiclass_dataset(
        pca_df, min_class_count=10, cap_threshold=1000, cap_per_class=1000
    )
    trained = training.train_random_forest_models(
        dataset, param_sets=[{"n_estimators": 10, "max_depth": 4, "random_state": 0}]
    )[0]

    models_dir = tmp_path / "models"
    version_dir = artifacts.next_version_dir(models_dir)
    metadata = artifacts.build_metadata(
        model_name=trained.name,
        dataset="synthetic-test-fixture",
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
    return version_dir


@pytest.fixture
def valid_feature_payload() -> dict:
    """A feature dict with every raw column the trained fixture model expects, all valid numeric values."""
    return {col: 0.5 for col in RAW_FEATURE_COLUMNS}
