"""
Feature selection for the IDS pipeline.

Implements:
1. Correlation-based filtering (|correlation| > 0.95)
2. Permutation importance ranking
3. Target: 25-40 features
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from sklearn.ensemble import RandomForestClassifier
from sklearn.inspection import permutation_importance
from sklearn.model_selection import train_test_split

from backend.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class FeatureSelectionResult:
    """Result of feature selection process."""
    selected_features: list[str]
    dropped_features: list[str]
    correlation_removed: list[str]
    importance_scores: dict[str, float]
    correlation_removed_pairs: list[tuple[str, str, float]]
    importance_ranking: list[tuple[str, float]]


def remove_highly_correlated_features(
    X: pd.DataFrame,
    threshold: float = 0.95,
    method: str = "pearson"
) -> tuple[pd.DataFrame, list[str], list[tuple[str, str, float]]]:
    """
    Remove features with correlation above threshold.
    
    Args:
        X: Feature DataFrame
        threshold: Correlation threshold (default 0.95)
        method: Correlation method ('pearson', 'spearman', 'kendall')
        
    Returns:
        (X_reduced, dropped_features, correlated_pairs)
    """
    logger.info(f"Removing features with |correlation| > {threshold}")
    
    # Compute correlation matrix
    corr_matrix = X.corr(method=method).abs()
    
    # Find highly correlated pairs
    upper_tri = corr_matrix.where(
        np.triu(np.ones(corr_matrix.shape), k=1).astype(bool)
    )
    
    # Find pairs above threshold
    high_corr_pairs = []
    for col in upper_tri.columns:
        for idx in upper_tri.index:
            if upper_tri.loc[idx, col] > threshold:
                # Keep the feature that appears first in the original order
                if col in X.columns and idx in X.columns:
                    # Keep the first one (lower index in original)
                    keep = col if list(X.columns).index(col) < list(X.columns).index(idx) else idx
                    drop = idx if keep == col else col
                    high_corr_pairs.append((keep, drop, upper_tri.loc[idx, col]))
    
    # Determine features to drop
    to_drop = set()
    for keep, drop, corr_val in high_corr_pairs:
        if drop not in to_drop:
            to_drop.add(drop)
    
    dropped = sorted(list(to_drop))
    X_reduced = X.drop(columns=to_drop)
    
    logger.info(f"Removed {len(dropped)} highly correlated features: {dropped}")
    
    return X.drop(columns=to_drop), dropped, [
        (keep, drop, corr) for keep, drop, corr in high_corr_pairs
    ]


def compute_permutation_importance(
    model: Any,
    X: pd.DataFrame,
    y: pd.Series,
    n_repeats: int = 10,
    random_state: int = 42,
    n_jobs: int = -1
) -> dict[str, float]:
    """
    Compute permutation importance for all features.
    
    Args:
        model: Fitted model with predict_proba method
        X: Feature DataFrame
        y: Target Series
        n_repeats: Number of permutations
        random_state: Random seed
        n_jobs: Number of parallel jobs
        
    Returns:
        Dictionary mapping feature name to importance score
    """
    logger.info("Computing permutation importance...")
    
    result = permutation_importance(
        model, X, y,
        n_repeats=n_repeats,
        random_state=random_state,
        n_jobs=-1,
        scoring='f1_macro'
    )
    
    importance = dict(zip(X.columns, result.importances_mean))
    return importance


def select_features_by_importance(
    X: pd.DataFrame,
    y: pd.Series,
    model: Any,
    target_n_features: int = 30,
    n_repeats: int = 10,
    random_state: int = 42,
) -> tuple[pd.DataFrame, list[str], dict[str, float]]:
    """
    Select top features by permutation importance.
    
    Args:
        X: Feature DataFrame
        y: Target Series
        model: Fitted model with predict_proba method
        target_n_features: Target number of features to keep
        n_repeats: Number of permutation repeats
        random_state: Random seed
        
    Returns:
        (X_selected, dropped_features, importance_scores)
    """
    logger.info(f"Selecting top {target_n_features} features by permutation importance")
    
    # Compute importance
    importance = compute_permutation_importance(
        model, X, y, n_repeats=n_repeats, random_state=42
    )
    
    # Rank features by importance
    ranked = sorted(importance.items(), key=lambda x: x[1], reverse=True)
    
    # Select top features
    selected = [name for name, _ in ranked[:target_n_features]]
    dropped = [name for name, _ in ranked[target_n_features:]]
    
    importance_scores = dict(ranked)
    
    logger.info(f"Selected {len(selected)} features, dropped {len(dropped)}")
    
    return X[list(selected)], [f for f in X.columns if f not in selected], importance_scores


def select_features_pipeline(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_val: pd.DataFrame,
    y_val: pd.Series,
    target_n_features: int = 30,
    correlation_threshold: float = 0.95,
    random_state: int = 42,
) -> FeatureSelectionResult:
    """
    Complete feature selection pipeline:
    1. Remove highly correlated features
    2. Train a baseline Random Forest
    3. Compute permutation importance
    4. Select top features by importance
    
    Args:
        X_train: Training features
        y_train: Training labels
        X_val: Validation features (for importance computation)
        y_val: Validation labels
        correlation_threshold: Correlation threshold for feature removal
        target_n_features: Target number of features to keep
        random_state: Random seed
        
    Returns:
        FeatureSelectionResult with selected features and metrics
    """
    logger.info(f"Starting feature selection pipeline (target: {target_n_features} features)")
    
    # Step 1: Remove highly correlated features
    X_train_corr, dropped_corr, corr_pairs = remove_highly_correlated_features(
        X_train, threshold=0.95
    )
    
    # Align validation set
    X_val_corr = X_val.drop(columns=[c for c in X_val.columns if c in dropped_corr], errors='ignore')
    
    # Step 2: Train baseline Random Forest for importance
    logger.info("Training baseline Random Forest for feature importance...")
    rf = RandomForestClassifier(
        n_estimators=100,
        max_depth=10,
        random_state=42,
        n_jobs=-1,
        class_weight="balanced"
    )
    rf.fit(X_train, y_train)
    
    # Step 3: Compute permutation importance on validation set
    importance = compute_permutation_importance(
        rf, X_val, y_val, n_repeats=10, random_state=42
    )
    
    # Step 4: Select top features by importance
    ranked = sorted(importance.items(), key=lambda x: x[1], reverse=True)
    
    # Ensure we keep at least the target number of features
    target_n = min(target_n_features, len(ranked))
    selected = [name for name, _ in ranked[:target_n_features]]
    dropped_imp = [name for name, _ in ranked[target_n_features:]]
    
    # Combine dropped features
    all_dropped = list(set(dropped_corr) | set(dropped_imp))
    all_selected = [c for c in X_train.columns if c not in all_dropped]
    
    # Build importance ranking
    importance_ranking = ranked
    importance_scores = dict(ranked)
    
    # Build correlation removed pairs
    corr_removed_pairs = [(keep, drop, corr) for keep, drop, corr in 
                          [("placeholder", "placeholder", 0.0)]  # placeholder
                         ][:0]  # empty list
    
    result = FeatureSelectionResult(
        selected_features=sorted(all_selected),
        dropped_features=sorted(all_dropped),
        correlation_removed=sorted(dropped_corr),
        importance_scores=importance_scores,
        correlation_removed_pairs=corr_removed_pairs,
        importance_ranking=importance_ranking,
    )
    
    logger.info(f"Feature selection complete: {len(importance_scores)} features evaluated, "
                f"{len(all_selected)} selected, {len(all_dropped)} dropped")
    
    return result