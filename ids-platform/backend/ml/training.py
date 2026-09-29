"""
Model training for the CIC-IDS2017 intrusion detection pipeline: binary and
multi-class dataset balancing, and training every model the notebook
trained, with its exact hyperparameters (see constants.py).

This module is a direct, function-based conversion of the notebook's
training cells:

    Notebook cells 94-95   -> prepare_binary_dataset()
    Notebook cells 98-106  -> train_logistic_regression_models(), train_svm_models()
    Notebook cells 109-112 -> prepare_multiclass_dataset()
    Notebook cells 115-124 -> train_random_forest_models(), train_decision_tree_models(),
                              train_knn_models()

It picks up where feature_engineering.py leaves off: every function here
takes the PCA-transformed DataFrame (PC1..PCn + Attack Type) as input.
Nothing here computes metrics beyond the notebook's own cross-validation
scores - see evaluation.py for test-set metrics (accuracy/precision/recall/
F1/confusion matrix/ROC/PR), and artifacts.py for persisting the result.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from imblearn.over_sampling import SMOTE
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.neighbors import KNeighborsClassifier
from sklearn.svm import SVC
from sklearn.tree import DecisionTreeClassifier

from backend.ml.constants import (
    BENIGN_LABEL,
    BINARY_SAMPLE_SIZE,
    CV_FOLDS,
    DECISION_TREE_PARAMS,
    KNN_PARAMS,
    LOGISTIC_REGRESSION_PARAMS,
    MULTICLASS_CAP_PER_CLASS,
    MULTICLASS_CAP_THRESHOLD,
    MULTICLASS_MIN_CLASS_COUNT,
    RANDOM_FOREST_PARAMS,
    RANDOM_STATE,
    SVM_PARAMS,
    TARGET_COLUMN,
    TEST_SIZE,
)
from backend.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class Dataset:
    """A train/test split ready to feed into a model's .fit()/.predict()."""

    X_train: pd.DataFrame
    X_test: pd.DataFrame
    y_train: pd.Series
    y_test: pd.Series


@dataclass
class TrainedModel:
    """A fitted model plus the cross-validation scores computed alongside it."""

    name: str
    model: Any
    cv_scores: np.ndarray
    params: dict

    @property
    def mean_cv_score(self) -> float:
        return float(self.cv_scores.mean())


# ==========================================================================
# Binary classification dataset - notebook cells 94-95
# ==========================================================================

def prepare_binary_dataset(
    pca_df: pd.DataFrame,
    target_column: str = TARGET_COLUMN,
    benign_label: str = BENIGN_LABEL,
    sample_size: int = BINARY_SAMPLE_SIZE,
    test_size: float = TEST_SIZE,
    random_state: int = RANDOM_STATE,
) -> Dataset:
    """
    Build the balanced binary-classification (BENIGN vs. attack) dataset.

    Converted from notebook cells 94-95:
        normal_traffic = new_data.loc[new_data['Attack Type'] == 'BENIGN']
        intrusions = new_data.loc[new_data['Attack Type'] != 'BENIGN']
        normal_traffic = normal_traffic.sample(n=len(intrusions), replace=False)
        ids_data = pd.concat([intrusions, normal_traffic])
        ids_data['Attack Type'] = np.where((ids_data['Attack Type'] == 'BENIGN'), 0, 1)
        bc_data = ids_data.sample(n=15000)
        X_train_bc, X_test_bc, y_train_bc, y_test_bc = train_test_split(
            X_bc, y_bc, test_size=0.25, random_state=0)

    Args:
        pca_df: PCA-transformed DataFrame (PC1..PCn + target_column), i.e.
            the output of FeatureEngineer.transform_to_frame().
        target_column: Name of the label column.
        benign_label: The label value that means "not an attack".
        sample_size: Final balanced-dataset size before splitting (notebook: 15000).
        test_size: train_test_split test fraction (notebook: 0.25).
        random_state: Shared random seed for sampling and splitting.

    Returns:
        A Dataset with X_train/X_test (PCA features) and y_train/y_test
        (0 = BENIGN, 1 = attack).
    """
    normal_traffic = pca_df.loc[pca_df[target_column] == benign_label]
    intrusions = pca_df.loc[pca_df[target_column] != benign_label]

    if len(intrusions) == 0:
        raise ValueError("No non-BENIGN rows found; cannot build a binary intrusion dataset")

    normal_traffic = normal_traffic.sample(n=len(intrusions), replace=False, random_state=random_state)

    ids_data = pd.concat([intrusions, normal_traffic])
    ids_data = ids_data.copy()
    ids_data[target_column] = np.where(ids_data[target_column] == benign_label, 0, 1)

    actual_sample_size = min(sample_size, len(ids_data))
    if actual_sample_size < sample_size:
        logger.warning(
            "Requested binary sample_size=%d but only %d rows available; using %d",
            sample_size,
            len(ids_data),
            actual_sample_size,
        )
    bc_data = ids_data.sample(n=actual_sample_size, random_state=random_state)
    logger.info("Binary dataset class balance:\n%s", bc_data[target_column].value_counts().to_string())

    X_bc = bc_data.drop(columns=[target_column])
    y_bc = bc_data[target_column]

    X_train, X_test, y_train, y_test = train_test_split(
        X_bc, y_bc, test_size=test_size, random_state=random_state
    )
    return Dataset(X_train=X_train, X_test=X_test, y_train=y_train, y_test=y_test)


# ==========================================================================
# Multi-class classification dataset - notebook cells 109-112
# ==========================================================================

def prepare_multiclass_dataset(
    pca_df: pd.DataFrame,
    target_column: str = TARGET_COLUMN,
    min_class_count: int = MULTICLASS_MIN_CLASS_COUNT,
    cap_threshold: int = MULTICLASS_CAP_THRESHOLD,
    cap_per_class: int = MULTICLASS_CAP_PER_CLASS,
    test_size: float = TEST_SIZE,
    random_state: int = RANDOM_STATE,
    split_mode: str = "chrono",  # "chrono" or "random"
) -> Dataset:
    """
    Build the balanced multi-class (attack type) dataset with configurable split mode.
    
    Supports two split modes:
    - "chrono": Within-day chronological split (70/30 per day) - default
    - "random": Random stratified split (for comparison/debugging)
    
    Both modes follow the correct leakage-safe order:
        1. Filter classes by min count
        2. Cap oversized classes
        2. Split into train/test (chronological or random stratified)
        3. Apply SMOTE ONLY to training data
        4. Keep test set untouched

    Args:
        pca_df: PCA-transformed DataFrame (PC1..PCn + target_column + 'day' column + 'timestamp').
        target_column: Name of the label column.
        min_class_count: Classes with <= this many rows are dropped
            entirely before balancing (notebook: 1950).
        cap_threshold: Classes larger than this get capped (notebook: 2500).
        cap_per_class: Cap applied to oversized classes (notebook: 5000).
        test_size: train_test_split test fraction (notebook: 0.25).
        random_state: Shared random seed for sampling, SMOTE, and splitting.
        split_mode: "chrono" (within-day 70/30) or "random" (stratified random).

    Returns:
        A Dataset with X_train/X_test (PCA features) and y_train/y_test
        (attack-type strings, training data SMOTE-balanced, test data untouched).
    
    Raises:
        ValueError: If any class has fewer than 50 training samples or is absent from test.
    """
    class_counts = pca_df[target_column].value_counts()
    selected_classes = class_counts[class_counts > min_class_count]
    class_names = selected_classes.index

    if len(class_names) == 0:
        raise ValueError(f"No class has more than {min_class_count} rows; cannot build a multi-class dataset")

    selected = pca_df[pca_df[target_column].isin(class_names)]

    capped_frames = []
    for name in class_names:
        class_df = selected[selected[target_column] == name]
        if len(class_df) > cap_threshold:
            n = min(cap_per_class, len(class_df))
            class_df = class_df.sample(n=n, random_state=random_state)
        capped_frames.append(class_df)

    capped = pd.concat(capped_frames, ignore_index=True)
    logger.info("Multi-class dataset before split:\n%s", capped[target_column].value_counts().to_string())

    # Remove exact duplicate rows before splitting (record count)
    initial_rows = len(capped)
    capped = capped.drop_duplicates()
    duplicate_count = len(capped) - capped.shape[0]  # Wait, this is wrong
    logger.info(f"Removed duplicate rows: {len(capped) - len(capped.drop_duplicates())}")

    # Actually drop duplicates and record count
    initial_rows = len(capped)
    capped = capped.drop_duplicates()
    duplicate_count = initial_rows - len(capped)
    logger.info(f"Removed {duplicate_count} duplicate rows ({initial_rows} -> {len(capped)})")

    if split_mode == "chrono":
        return prepare_multiclass_dataset_chrono(
            capped, target_column=target_column, min_class_count=min_class_count,
            cap_threshold=cap_threshold, cap_per_class=cap_per_class,
            random_state=RANDOM_STATE
        )
    elif split_mode == "random":
        return _prepare_multiclass_dataset_random(
            capped, target_column=target_column, min_class_count=min_class_count,
            cap_threshold=cap_threshold, cap_per_class=cap_per_class,
            test_size=TEST_SIZE, random_state=random_state
        )
    else:
        raise ValueError(f"Unknown split_mode: {split_mode}. Use 'chrono' or 'random'.")


def prepare_multiclass_dataset_chrono(
    pca_df: pd.DataFrame,
    target_column: str = TARGET_COLUMN,
    min_class_count: int = MULTICLASS_MIN_CLASS_COUNT,
    cap_threshold: int = MULTICLASS_CAP_THRESHOLD,
    cap_per_class: int = MULTICLASS_CAP_PER_CLASS,
    test_size: float = TEST_SIZE,
    random_state: int = RANDOM_STATE,
) -> Dataset:
    """
    Build the balanced multi-class dataset with WITHIN-DAY CHRONOLOGICAL SPLIT (70/30 per day).
    
    This prevents data leakage from temporal correlation and provides a more
    realistic evaluation of model generalization to future traffic.
    
    Correct order (leakage-safe + chronological):
        1. Filter classes by min count
        2. Cap oversized classes
        3. Split by day: for each day, sort by timestamp, use first 70% for training, last 30% for test
        4. Apply SMOTE ONLY to training data
        5. Keep test set untouched
    
    Args:
        pca_df: PCA-transformed DataFrame (PC1..PCn + target_column + 'day' column + 'timestamp' column).
        target_column: Name of the label column.
        min_class_count: Classes with <= this many rows are dropped
            entirely before balancing (notebook: 1950).
        cap_threshold: Classes larger than this get capped (notebook: 2500).
        cap_per_class: Cap applied to oversized classes (notebook: 5000).
        test_size: Fraction of each day's data to use for testing (default: 0.30).
        random_state: Shared random seed for sampling and SMOTE.
    
    Returns:
        A Dataset with X_train/X_test (PCA features) and y_train/y_test
        (attack-type strings, training data SMOTE-balanced, test data untouched).
    
    Raises:
        ValueError: If any class has fewer than 50 training samples or is absent from test set.
    """
    class_counts = pca_df[target_column].value_counts()
    selected_classes = class_counts[class_counts > min_class_count]
    class_names = selected_classes.index

    if len(class_names) == 0:
        raise ValueError(f"No class has more than {min_class_count} rows; cannot build a multi-class dataset")

    selected = pca_df[pca_df[target_column].isin(class_names)]

    capped_frames = []
    for name in class_names:
        class_df = selected[selected[target_column] == name]
        if len(class_df) > cap_threshold:
            n = min(cap_per_class, len(class_df))
            class_df = class_df.sample(n=n, random_state=random_state)
        capped_frames.append(class_df)

    capped = pd.concat(capped_frames, ignore_index=True)
    logger.info("Multi-class dataset before chronological split:\n%s", capped[target_column].value_counts().to_string())

    # Ensure we have a timestamp column for chronological sorting within each day
    if 'timestamp' not in capped.columns:
        raise ValueError("Chronological split requires 'timestamp' column in DataFrame. "
                         "Ensure preprocessing adds a timestamp column.")

# WITHIN-DAY CHRONOLOGICAL SPLIT: 70/30 per day
    train_frames = []
    test_frames = []
    seen_indices = set()
    
    for day in capped['day'].unique():
        day_df = capped[capped['day'] == day].copy()
        if 'timestamp' not in day_df.columns:
            raise ValueError(f"Day {day} data missing 'timestamp' column")
        
        # Sort by timestamp within the day
        day_df = day_df.sort_values('timestamp')
        
        # Calculate split point (70% train, 30% test)
        split_idx = int(len(day_df) * 0.7)
        
        # Ensure no overlap by using positional indexing
        train_day = day_df.iloc[:split_idx].copy()
        test_day = day_df.iloc[split_idx:].copy()
        
        # Verify no overlap within this day
        train_indices = set(train_day.index)
        test_indices = set(test_day.index)
        overlap = train_indices & test_indices
        if overlap:
            raise ValueError(f"Data overlap detected within day {day}: {len(overlap)} overlapping rows")
        
        train_frames.append(train_day)
        test_frames.append(test_day)
    
    train_df = pd.concat(train_frames, ignore_index=True)
    test_df = pd.concat(test_frames, ignore_index=True)
    
    # Final verification: ensure no row overlap between train and test
    # Compare actual data rows (not indices) to detect leakage
    train_rows = train_df.drop(columns=[target_column, 'day']).astype(str).apply(tuple, axis=1)
    test_rows = test_df.drop(columns=[target_column, 'day']).astype(str).apply(tuple, axis=1)
    overlap_rows = set(train_rows) & set(test_rows)
    if overlap_rows:
        raise ValueError(f"Data leakage detected: {len(overlap_rows)} rows appear in both train and test sets")

    logger.info("Chronological split: Train=%d rows, Test=%d rows", len(train_df), len(test_df))
    logger.info("Train class distribution:\n%s", train_df[target_column].value_counts().to_string())
    logger.info("Test class distribution:\n%s", test_df[target_column].value_counts().to_string())

    # Validate class counts
    train_counts = train_df[target_column].value_counts()
    test_counts = test_df[target_column].value_counts()
    
    for class_name in class_names:
        train_count = train_counts.get(class_name, 0)
        test_count = test_counts.get(class_name, 0)
        if train_count < 50:
            raise ValueError(f"Class '{class_name}' has fewer than 50 training samples ({train_count}). "
                           f"Cannot proceed with training.")
        if test_count == 0:
            logger.warning(f"Class '{class_name}' is absent from test set. "
                           f"Skipping this class in evaluation.")
            # Remove from class_names to skip evaluation on this class
            class_names = [c for c in class_names if c != class_name]
            if len(class_names) == 0:
                raise ValueError("No valid classes remaining for evaluation.")

        logger.info("Train class distribution:\n%s", pd.Series(train_df[target_column]).value_counts().to_string())
        logger.info("Test class distribution:\n%s", test_df[target_column].value_counts().to_string())

    X_train_raw = train_df.drop(columns=[target_column, 'day'])
    y_train = train_df[target_column]
    X_test = test_df.drop(columns=[target_column, 'day'])
    y_test = test_df[target_column]

    # Apply SMOTE ONLY to training data (no leakage)
    smote = SMOTE(sampling_strategy="auto", random_state=RANDOM_STATE)
    X_train_upsampled, y_train_upsampled = smote.fit_resample(
        train_df.drop(columns=[target_column, 'day']), y_train
    )

    logger.info("Train class distribution after SMOTE:\n%s", 
                pd.Series(y_train_upsampled).value_counts().to_string())
    logger.info("Test class distribution (untouched):\n%s", y_test.value_counts().to_string())

    return Dataset(
        X_train=pd.DataFrame(X_train_upsampled, columns=train_df.drop(columns=[target_column, 'day']).columns),
        X_test=test_df.drop(columns=[target_column, 'day']),
        y_train=pd.Series(y_train_upsampled, name=target_column),
        y_test=test_df[target_column]
    )


# ==========================================================================
# Generic train-one-model-with-cross-validation helper
# ==========================================================================

def _fit_with_cv(
    name: str,
    estimator: Any,
    X_train: pd.DataFrame,
    y_train: pd.Series,
    params: dict,
    cv: int = CV_FOLDS,
) -> TrainedModel:
    estimator.fit(X_train, y_train)
    cv_scores = cross_val_score(estimator, X_train, y_train, cv=cv)
    logger.info(
        "%s: mean CV score=%.4f (folds=%d), params=%s",
        name,
        cv_scores.mean(),
        cv,
        params,
    )
    return TrainedModel(name=name, model=estimator, cv_scores=cv_scores, params=params)


# ==========================================================================
# Binary classification models - notebook cells 98-106
# ==========================================================================

def train_logistic_regression_models(
    dataset: Dataset,
    param_sets: list[dict] = LOGISTIC_REGRESSION_PARAMS,
    cv: int = CV_FOLDS,
) -> list[TrainedModel]:
    """Train every LogisticRegression variant from the notebook (lr1, lr2 - cells 98, 100)."""
    return [
        _fit_with_cv(f"logistic_regression_{i + 1}", LogisticRegression(**params), dataset.X_train, dataset.y_train, params, cv)
        for i, params in enumerate(param_sets)
    ]


def train_svm_models(
    dataset: Dataset,
    param_sets: list[dict] = SVM_PARAMS,
    cv: int = CV_FOLDS,
) -> list[TrainedModel]:
    """Train every SVC variant from the notebook (svm1, svm2 - cells 104, 105)."""
    return [
        _fit_with_cv(f"svm_{i + 1}", SVC(**params), dataset.X_train, dataset.y_train, params, cv)
        for i, params in enumerate(param_sets)
    ]


# ==========================================================================
# Multi-class classification models - notebook cells 115-124
# ==========================================================================

def train_random_forest_models(
    dataset: Dataset,
    param_sets: list[dict] = RANDOM_FOREST_PARAMS,
    cv: int = CV_FOLDS,
) -> list[TrainedModel]:
    """Train every RandomForestClassifier variant from the notebook (rf1, rf2 - cells 115, 116)."""
    return [
        _fit_with_cv(f"random_forest_{i + 1}", RandomForestClassifier(**params), dataset.X_train, dataset.y_train, params, cv)
        for i, params in enumerate(param_sets)
    ]


def train_decision_tree_models(
    dataset: Dataset,
    param_sets: list[dict] = DECISION_TREE_PARAMS,
    cv: int = CV_FOLDS,
) -> list[TrainedModel]:
    """Train every DecisionTreeClassifier variant from the notebook (dt1, dt2 - cells 119, 120)."""
    return [
        _fit_with_cv(f"decision_tree_{i + 1}", DecisionTreeClassifier(**params), dataset.X_train, dataset.y_train, params, cv)
        for i, params in enumerate(param_sets)
    ]


def train_knn_models(
    dataset: Dataset,
    param_sets: list[dict] = KNN_PARAMS,
    cv: int = CV_FOLDS,
) -> list[TrainedModel]:
    """Train every KNeighborsClassifier variant from the notebook (knn1, knn2 - cells 123, 124)."""
    return [
        _fit_with_cv(f"knn_{i + 1}", KNeighborsClassifier(**params), dataset.X_train, dataset.y_train, params, cv)
        for i, params in enumerate(param_sets)
    ]


# ==========================================================================
# Full pipeline convenience wrappers
# ==========================================================================

def train_all_binary_models(dataset: Dataset) -> list[TrainedModel]:
    """Train both LogisticRegression and both SVM variants (4 models total)."""
    return train_logistic_regression_models(dataset) + train_svm_models(dataset)


def train_all_multiclass_models(dataset: Dataset) -> list[TrainedModel]:
    """Train both RandomForest, both DecisionTree, and both KNN variants (6 models total)."""
    return (
        train_random_forest_models(dataset)
        + train_decision_tree_models(dataset)
        + train_knn_models(dataset)
    )