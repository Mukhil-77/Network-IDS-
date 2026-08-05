"""
Feature engineering for the CIC-IDS2017 intrusion detection pipeline:
scaling and dimensionality reduction.

This module is a direct, function-based conversion of the notebook's
feature-engineering cells:

    Notebook cell 85  -> split_features_and_target(), fit_scaler(), scale_features()
    Notebook cell 86  -> fit_incremental_pca()
    Notebook cell 87  -> transform_with_pca(), pca_column_names()

It builds on backend.ml.preprocessing (Milestone 1): preprocessing.py hands
off a cleaned DataFrame with a grouped `Attack Type` column, and this module
picks up from there - scaling, then Incremental PCA, exactly as the
notebook does. No model training happens here; see training.py.

The `FeatureEngineer` class bundles the fitted StandardScaler + IncrementalPCA
together as one reusable, save/load-able unit, since in production they must
always travel together (a PCA fitted on one scaler's output is meaningless
with another scaler). Persistence itself (the actual pickling/JSON I/O) is
delegated to artifacts.py so that logic exists in exactly one place.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from sklearn.decomposition import IncrementalPCA
from sklearn.preprocessing import StandardScaler

from backend.ml.constants import IPCA_BATCH_SIZE, TARGET_COLUMN
from backend.utils.logger import get_logger

logger = get_logger(__name__)


def split_features_and_target(
    df: pd.DataFrame,
    target_column: str = TARGET_COLUMN,
) -> tuple[pd.DataFrame, pd.Series]:
    """
    Split a preprocessed DataFrame into a feature matrix and target series.

    Converted from notebook cell 85 (`features = data.drop('Attack Type',
    axis=1)`, `attacks = data['Attack Type']`).

    Args:
        df: Cleaned DataFrame from preprocessing.preprocess_dataset(), still
            containing `target_column`.
        target_column: Name of the label column to split off.

    Returns:
        (X, y) - feature DataFrame and target Series.

    Raises:
        KeyError: If `target_column` is not present in `df`.
    """
    if target_column not in df.columns:
        raise KeyError(f"Expected target column '{target_column}' not found in DataFrame")

    X = df.drop(columns=[target_column])
    y = df[target_column]
    logger.info("Split features/target -> X: %d cols, y: '%s' (%d rows)", X.shape[1], target_column, len(y))
    return X, y


def fit_scaler(X: pd.DataFrame) -> StandardScaler:
    """
    Fit a StandardScaler on the feature matrix.

    Converted from notebook cell 85 (`scaler = StandardScaler();
    scaled_features = scaler.fit_transform(features)`) - fitting is split
    out from transforming here so the same fitted scaler can be reused for
    both the training transform and every future inference-time transform.
    """
    scaler = StandardScaler()
    scaler.fit(X)
    logger.info("Fitted StandardScaler on %d feature(s)", X.shape[1])
    return scaler


def scale_features(scaler: StandardScaler, X: pd.DataFrame) -> np.ndarray:
    """Apply an already-fitted StandardScaler to a feature matrix."""
    return scaler.transform(X)


def fit_incremental_pca(
    scaled_features: np.ndarray,
    n_features: int,
    batch_size: int = IPCA_BATCH_SIZE,
) -> IncrementalPCA:
    """
    Fit an IncrementalPCA model via partial_fit batches, mirroring the
    notebook's memory-efficient approach for a dataset too large to fit PCA
    on all at once.

    Converted from notebook cell 86:
        size = len(features.columns) // 2
        ipca = IncrementalPCA(n_components=size, batch_size=500)
        for batch in np.array_split(scaled_features, len(features) // 500):
            ipca.partial_fit(batch)

    Args:
        scaled_features: Output of scale_features() - the standardized
            feature matrix.
        n_features: Number of columns in the original (unscaled) feature
            matrix. Used to derive n_components = n_features // 2, exactly
            as the notebook does (kept as a caller-supplied argument rather
            than inferred from `scaled_features.shape[1]` so the two stay
            unambiguously in sync with the DataFrame the caller is
            reasoning about).
        batch_size: Rows per partial_fit batch. Defaults to
            constants.IPCA_BATCH_SIZE (500, matching the notebook).

    Returns:
        A fitted IncrementalPCA instance.
    """
    n_components = n_features // 2
    n_rows = scaled_features.shape[0]
    n_batches = max(n_rows // batch_size, 1)

    ipca = IncrementalPCA(n_components=n_components, batch_size=batch_size)
    for batch in np.array_split(scaled_features, n_batches):
        ipca.partial_fit(batch)

    retained = float(np.sum(ipca.explained_variance_ratio_))
    logger.info(
        "Fitted IncrementalPCA: n_components=%d, batches=%d, information retained=%.2f%%",
        n_components,
        n_batches,
        retained * 100,
    )
    return ipca


def pca_column_names(n_components: int) -> list[str]:
    """Return the PC1..PCn column names used for the transformed feature space."""
    return [f"PC{i + 1}" for i in range(n_components)]


def transform_with_pca(
    ipca: IncrementalPCA,
    scaled_features: np.ndarray,
    target: Optional[pd.Series] = None,
    target_column: str = TARGET_COLUMN,
) -> pd.DataFrame:
    """
    Project standardized features into PCA space and return them as a
    labeled DataFrame.

    Converted from notebook cell 87:
        transformed_features = ipca.transform(scaled_features)
        new_data = pd.DataFrame(transformed_features, columns=[f'PC{i+1}' ...])
        new_data['Attack Type'] = attacks.values

    Args:
        ipca: A fitted IncrementalPCA (from fit_incremental_pca()).
        scaled_features: Standardized feature matrix to transform.
        target: Optional target Series to attach as `target_column`. Pass
            None for inference, where there is no label yet.
        target_column: Name to give the re-attached label column.

    Returns:
        DataFrame with columns PC1..PCn (+ `target_column` if `target` was
        given).
    """
    transformed = ipca.transform(scaled_features)
    columns = pca_column_names(ipca.n_components_)
    result = pd.DataFrame(transformed, columns=columns)

    if target is not None:
        result[target_column] = target.values

    return result


@dataclass
class FeatureEngineer:
    """
    Bundles a fitted StandardScaler + IncrementalPCA as a single reusable
    transform, so training and inference can never accidentally apply a
    scaler and a PCA that weren't fitted together.

    Usage:
        fe = FeatureEngineer.fit(X)
        pca_df = fe.transform_to_frame(X, target=y)
        ...
        fe.save(version_dir)          # delegates to artifacts.py
        fe = FeatureEngineer.load(version_dir)  # delegates to artifacts.py
    """

    scaler: StandardScaler
    pca: IncrementalPCA

    @classmethod
    def fit(cls, X: pd.DataFrame, batch_size: int = IPCA_BATCH_SIZE) -> "FeatureEngineer":
        """Fit a new StandardScaler + IncrementalPCA pair on `X`."""
        scaler = fit_scaler(X)
        scaled = scale_features(scaler, X)
        pca = fit_incremental_pca(scaled, n_features=X.shape[1], batch_size=batch_size)
        return cls(scaler=scaler, pca=pca)

    def transform(self, X: pd.DataFrame) -> np.ndarray:
        """Scale then PCA-transform a feature matrix, returning a raw ndarray."""
        scaled = scale_features(self.scaler, X)
        return self.pca.transform(scaled)

    def transform_to_frame(
        self,
        X: pd.DataFrame,
        target: Optional[pd.Series] = None,
        target_column: str = TARGET_COLUMN,
    ) -> pd.DataFrame:
        """Scale then PCA-transform a feature matrix, returning a labeled DataFrame."""
        scaled = scale_features(self.scaler, X)
        return transform_with_pca(self.pca, scaled, target=target, target_column=target_column)

    @property
    def feature_names(self) -> list[str]:
        """PC1..PCn names for the fitted PCA's output space."""
        return pca_column_names(self.pca.n_components_)

    def save(self, version_dir: str | Path) -> None:
        """Persist scaler + PCA + feature names into `version_dir`. See artifacts.py."""
        from backend.ml import artifacts  # local import: avoids a circular import at module load time

        artifacts.save_scaler(self.scaler, version_dir)
        artifacts.save_pca(self.pca, version_dir)
        artifacts.save_feature_names(self.feature_names, version_dir)

    @classmethod
    def load(cls, version_dir: str | Path) -> "FeatureEngineer":
        """Load a previously-saved scaler + PCA pair from `version_dir`. See artifacts.py."""
        from backend.ml import artifacts  # local import: avoids a circular import at module load time

        return cls(
            scaler=artifacts.load_scaler(version_dir),
            pca=artifacts.load_pca(version_dir),
        )
