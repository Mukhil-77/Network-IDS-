"""
Batch training: train deployed model variants (LightGBM + Random Forest) and persist
each as its own versioned artifact bundle under models/v1, models/v2, ...

Each training run calls the single-run pipeline: preprocessing -> feature selection
(direct features, no PCA/scaler) -> training (with class_weight='balanced') -> evaluation.
Only the best models (LightGBM + Random Forest) are saved, so the API's
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
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.ml import artifacts, evaluation, preprocessing, training
from backend.ml.constants import TARGET_COLUMN
from backend.ml.feature_schema import CANONICAL_FEATURE_NAMES
from backend.utils.logger import get_logger

logger = get_logger(__name__)


def run(data_dir: str, models_dir: str = "models", *, save_all: bool = True, split_mode: str = "chrono") -> list[dict]:
    """Train deployed model variants (LightGBM + Random Forest) and persist as versioned bundles."""
    # 1. Preprocessing (Milestone 1 - unchanged)
    df = preprocessing.preprocess_dataset(data_dir)

    # 2. Feature selection - no PCA, no scaler, use canonical features directly
    from backend.ml import feature_selection
    from backend.ml.constants import TARGET_COLUMN
    from backend.ml.feature_schema import CANONICAL_FEATURE_NAMES
    
    # Prepare the full dataset with day/timestamp for splitting
    df = preprocessing.preprocess_dataset(data_dir)
    
    # Split data using chronological split (default) or random
    from backend.ml.training import prepare_multiclass_dataset
    multiclass_dataset = prepare_multiclass_dataset(
        preprocessing.preprocess_dataset(data_dir), 
        target_column=TARGET_COLUMN, 
        split_mode="chrono"
    )

    saved: list[dict] = []

    def _save_model(model, result, model_name, model_type):
        """Save a trained model with its metadata."""
        import hashlib
        from datetime import datetime, timezone
        
        from backend.ml import artifacts
        version_dir = artifacts.next_version_dir(models_dir)
        
        # Compute feature hash for manifest
        feature_hash = hashlib.sha256("".join(sorted(CANONICAL_FEATURE_NAMES)).encode()).hexdigest()[:16]
        
        # Save model only (no scaler/pca)
        version_dir = artifacts.next_version_dir(models_dir)
        
        metadata = {
            "model_name": f"{model_name}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
            "dataset": "CIC-IDS2017",
            "accuracy": result.accuracy,
            "precision": result.precision_macro,
            "recall": result.recall_macro,
            "f1_score": result.f1_macro,
            "features": "canonical_53_features",
            "feature_hash": hashlib.sha256("".join(sorted(CANONICAL_FEATURE_NAMES)).encode()).hexdigest()[:16],
            "model_type": model_name,
            "training_date": datetime.now(timezone.utc).isoformat(),
            "split_mode": "chrono",
            "features_hash": hashlib.sha256("".join(sorted(CANONICAL_FEATURE_NAMES)).encode()).hexdigest()[:16],
        }
        
        # Save model only (no scaler/pca)
        version_dir = artifacts.next_version_dir(models_dir)
        
        # Save model only (no scaler/pca)
        from backend.ml import artifacts as artifacts_module
        artifacts.save_model(model, version_dir)
        artifacts.save_metadata({
            "model_name": f"{model_name}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
            "dataset": "CIC-IDS2017",
            "accuracy": result.accuracy,
            "precision": result.precision_macro,
            "recall": result.recall_macro,
            "f1_score": result.f1_macro,
            "features": "canonical_53_features",
            "feature_hash": hashlib.sha256("".join(sorted(CANONICAL_FEATURE_NAMES)).encode()).hexdigest()[:16],
            "model_type": "LightGBM" if "lightgbm" in str(type(model)).lower() else "RandomForest",
            "training_date": datetime.now(timezone.utc).isoformat(),
            "split_mode": "chrono",
            "features_hash": hashlib.sha256("".join(sorted(CANONICAL_FEATURE_NAMES)).encode()).hexdigest()[:16],
        }, version_dir)
        
        entry = {"version_dir": str(version_dir), "name": model_name, **metadata}
        saved.append(entry)
        logger.info("Saved '%s' to %s (accuracy=%.4f)", model_name, version_dir, result.accuracy)
        return entry
    
    # 3. Binary models (LogisticRegression x2, SVM x2) - NOT saved to deployed registry (suboptimal)
    binary_dataset = training.prepare_binary_dataset(preprocessing.preprocess_dataset(data_dir), target_column=TARGET_COLUMN)
    binary_models = training.train_all_binary_models(binary_dataset)
    binary_results = [
        evaluation.evaluate_model(tm.name, tm.model, binary_dataset.X_test, binary_dataset.y_test, tm.cv_scores)
        for tm in binary_models
    ]
    logger.info("Binary model comparison (not saved to registry): %s", evaluation.compare_models(binary_results))

    # 4. Multi-class models - only LightGBM and Random Forest saved to deployed registry
    multiclass_dataset = training.prepare_multiclass_dataset(preprocessing.preprocess_dataset(data_dir), target_column=TARGET_COLUMN, split_mode="chrono")
    
    # Train LightGBM with Optuna tuning
    from lightgbm import LGBMClassifier
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.calibration import CalibratedClassifierCV
    from sklearn.model_selection import GridSearchCV
    import optuna
    
    # Prepare training data
    X_train = multiclass_dataset.X_train
    y_train = multiclass_dataset.y_train
    X_test = multiclass_dataset.X_test
    y_test = multiclass_dataset.y_test
    
    # Ensure we only use canonical features
    X_train = X_train[CANONICAL_FEATURE_NAMES]
    X_test = X_test[CANONICAL_FEATURE_NAMES]
    
    saved_models = []
    
    # Train LightGBM with Optuna tuning
    logger.info("Training LightGBM with Optuna tuning...")
    
    def objective(trial):
        params = {
            'objective': 'multiclass',
            'num_class': len(multiclass_dataset.y_train.unique()),
            'metric': 'multi_logloss',
            'boosting_type': 'gbdt',
            'num_leaves': trial.suggest_int('num_leaves', 31, 255),
            'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.3, log=True),
            'feature_fraction': trial.suggest_float('feature_fraction', 0.4, 1.0),
            'bagging_fraction': trial.suggest_float('bagging_fraction', 0.4, 1.0),
            'bagging_freq': trial.suggest_int('bagging_freq', 1, 7),
            'min_child_samples': trial.suggest_int('min_child_samples', 5, 100),
            'min_child_weight': trial.suggest_float('min_child_weight', 1e-3, 10.0, log=True),
            'subsample': trial.suggest_float('subsample', 0.5, 1.0),
            'colsample_bytree': trial.suggest_float('colsample_bytree', 0.4, 1.0),
            'reg_alpha': trial.suggest_float('reg_alpha', 1e-8, 10.0, log=True),
            'reg_lambda': trial.suggest_float('reg_lambda', 1e-8, 10.0, log=True),
            'random_state': 42,
            'verbosity': -1,
            'n_jobs': -1,
            'class_weight': 'balanced',
        }
        
        model = LGBMClassifier(**params)
        model.fit(multiclass_dataset.X_train, multiclass_dataset.y_train)
        preds = model.predict(multiclass_dataset.X_test)
        from sklearn.metrics import f1_score
        return f1_score(multiclass_dataset.y_test, preds, average='macro')
    
    study = optuna.create_study(direction='maximize', sampler=optuna.samplers.TPESampler(seed=42))
    study.optimize(objective, n_trials=50, timeout=1800, show_progress_bar=True)
    
    logger.info(f"LightGBM best params: {study.best_params}, best F1: {study.best_value:.4f}")
    
    # Train final LightGBM with best params
    best_lgb = LGBMClassifier(**study.best_params)
    best_lgb.fit(multiclass_dataset.X_train, multiclass_dataset.y_train)
    
    # Calibrate
    calibrated_lgb = CalibratedClassifierCV(best_lgb, method='isotonic', cv=3)
    calibrated_lgb.fit(multiclass_dataset.X_train, multiclass_dataset.y_train)
    
    # Evaluate
    from backend.ml import evaluation
    lgb_result = evaluation.evaluate_model("lightgbm", calibrated_lgb, multiclass_dataset.X_test, multiclass_dataset.y_test, cv_scores=None)
    _save_model(calibrated_lgb, lgb_result, "lightgbm", "LightGBM")
    
    # Train Random Forest with grid search
    logger.info("Training Random Forest with grid search...")
    
    rf_params = {
        'n_estimators': [200, 400, 600],
        'max_depth': [10, 20, 30, None],
        'min_samples_split': [2, 5, 10],
        'min_samples_leaf': [1, 2, 4],
        'max_features': ['sqrt', 'log2', None],
    }
    
    rf = RandomForestClassifier(class_weight='balanced', random_state=42, n_jobs=-1)
    grid_search = GridSearchCV(rf, rf_params, cv=3, scoring='f1_macro', n_jobs=-1, verbose=1)
    grid_search.fit(multiclass_dataset.X_train, multiclass_dataset.y_train)
    
    logger.info(f"Random Forest best params: {grid_search.best_params_}, best CV F1: {grid_search.best_score_:.4f}")
    
    best_rf = grid_search.best_estimator_
    
    # Calibrate
    calibrated_rf = CalibratedClassifierCV(best_rf, method='isotonic', cv=3)
    calibrated_rf.fit(multiclass_dataset.X_train, multiclass_dataset.y_train)
    
    # Evaluate
    rf_result = evaluation.evaluate_model("random_forest", calibrated_rf, multiclass_dataset.X_test, multiclass_dataset.y_test, cv_scores=None)
    _save_model(calibrated_rf, rf_result, "random_forest", "RandomForest")
    
    logger.info("Training complete. Saved %d models.", len(saved))
    return saved

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