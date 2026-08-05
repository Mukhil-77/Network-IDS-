"""
Unit tests for backend/ml/feature_engineering.py.

Uses small, hand-built synthetic feature matrices (not the real CIC-IDS2017
data) so these run in milliseconds. IncrementalPCA needs at least
`n_components` rows per partial_fit batch, so the synthetic data here is
sized accordingly.

Run with:
    python -m pytest tests/test_feature_engineering.py -v
"""

import numpy as np
import pandas as pd
import pytest

from backend.ml.feature_engineering import (
    FeatureEngineer,
    fit_incremental_pca,
    fit_scaler,
    pca_column_names,
    scale_features,
    split_features_and_target,
    transform_with_pca,
)


def _make_synthetic_df(n_rows: int = 200, n_features: int = 6) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    data = rng.normal(size=(n_rows, n_features))
    df = pd.DataFrame(data, columns=[f"feat_{i}" for i in range(n_features)])
    df["Attack Type"] = ["BENIGN" if i % 2 == 0 else "DoS" for i in range(n_rows)]
    return df


# --------------------------------------------------------------------------
# split_features_and_target
# --------------------------------------------------------------------------

def test_split_features_and_target_separates_columns():
    df = _make_synthetic_df()
    X, y = split_features_and_target(df, target_column="Attack Type")

    assert "Attack Type" not in X.columns
    assert list(y.unique()) == ["BENIGN", "DoS"]
    assert len(X) == len(y) == len(df)


def test_split_features_and_target_raises_on_missing_column():
    df = _make_synthetic_df()
    with pytest.raises(KeyError):
        split_features_and_target(df, target_column="does_not_exist")


# --------------------------------------------------------------------------
# fit_scaler / scale_features
# --------------------------------------------------------------------------

def test_fit_scaler_produces_standardized_output():
    df = _make_synthetic_df()
    X, _ = split_features_and_target(df)

    scaler = fit_scaler(X)
    scaled = scale_features(scaler, X)

    assert scaled.shape == X.shape
    # Standardized data should have ~zero mean and ~unit variance per column.
    assert np.allclose(scaled.mean(axis=0), 0, atol=1e-6)
    assert np.allclose(scaled.std(axis=0), 1, atol=1e-6)


# --------------------------------------------------------------------------
# fit_incremental_pca / transform_with_pca
# --------------------------------------------------------------------------

def test_fit_incremental_pca_uses_half_the_features_as_components():
    df = _make_synthetic_df(n_rows=200, n_features=6)
    X, y = split_features_and_target(df)
    scaler = fit_scaler(X)
    scaled = scale_features(scaler, X)

    ipca = fit_incremental_pca(scaled, n_features=X.shape[1], batch_size=50)

    assert ipca.n_components_ == X.shape[1] // 2


def test_transform_with_pca_returns_labeled_dataframe():
    df = _make_synthetic_df(n_rows=200, n_features=6)
    X, y = split_features_and_target(df)
    scaler = fit_scaler(X)
    scaled = scale_features(scaler, X)
    ipca = fit_incremental_pca(scaled, n_features=X.shape[1], batch_size=50)

    result = transform_with_pca(ipca, scaled, target=y)

    assert list(result.columns) == pca_column_names(ipca.n_components_) + ["Attack Type"]
    assert len(result) == len(df)


def test_transform_with_pca_omits_target_column_when_not_given():
    df = _make_synthetic_df(n_rows=200, n_features=6)
    X, _ = split_features_and_target(df)
    scaler = fit_scaler(X)
    scaled = scale_features(scaler, X)
    ipca = fit_incremental_pca(scaled, n_features=X.shape[1], batch_size=50)

    result = transform_with_pca(ipca, scaled, target=None)

    assert "Attack Type" not in result.columns


# --------------------------------------------------------------------------
# FeatureEngineer (fit / transform / save / load)
# --------------------------------------------------------------------------

def test_feature_engineer_fit_and_transform_roundtrip():
    df = _make_synthetic_df(n_rows=200, n_features=6)
    X, y = split_features_and_target(df)

    fe = FeatureEngineer.fit(X, batch_size=50)
    pca_df = fe.transform_to_frame(X, target=y)

    assert list(pca_df.columns) == fe.feature_names + ["Attack Type"]
    assert len(pca_df) == len(df)


def test_feature_engineer_save_and_load_roundtrip(tmp_path):
    df = _make_synthetic_df(n_rows=200, n_features=6)
    X, y = split_features_and_target(df)

    fe = FeatureEngineer.fit(X, batch_size=50)
    fe.save(tmp_path)

    loaded = FeatureEngineer.load(tmp_path)
    original_transform = fe.transform(X)
    loaded_transform = loaded.transform(X)

    assert np.allclose(original_transform, loaded_transform)
