"""
Leave-One-Class-Out (LOCO) Experiment for Zero-Day Detection Evaluation.

For each attack family:
1. Remove that attack class from training data
2. Retrain supervised model and anomaly detector
3. Test on the held-out attack class + benign
4. Measure: recall of "flagged" on held-out class, benign FPR

This evaluates the system's ability to detect truly unseen attacks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from sklearn.ensemble import RandomForestClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.model_selection import train_test_split

from backend.ml import preprocessing
from backend.ml.training import prepare_multiclass_dataset
from backend.ml.anomaly_detection import IsolationForestDetector, ZeroDayDetector, create_zero_day_detector
from backend.ml.calibration import calibrate_model
from backend.ml.training import prepare_multiclass_dataset
from backend.ml.feature_selection import select_features_pipeline
from backend.ml.calibration import calibrate_model

from backend.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class LOCOResult:
    """Results of leave-one-class-out experiment for one attack family."""
    held_out_class: str
    # Training set stats
    train_samples: int
    train_classes: int
    # Test set stats
    test_samples: int
    held_out_test_samples: int
    benign_test_samples: int
    # Detection metrics
    held_out_recall: float          # Recall on held-out attack class
    benign_fpr: float               # False positive rate on benign
    held_out_precision: float       # Precision on held-out class
    held_out_f1: float              # F1 on held-out class
    # Zero-day detection
    zero_day_recall: float          # Recall of "zero-day" flag on held-out class
    zero_day_precision: float
    zero_day_f1: float
    # Benign FPR
    benign_fpr: float
    # Calibrated thresholds
    t_conf: float
    t_anom: float
    # Timing
    train_time_seconds: float
    test_time_seconds: float


def run_loco_experiment(
    data_dir: str,
    attack_families: List[str],
    target_column: str = "Attack Type",
    split_mode: str = "chrono",
    contamination: float = 0.01,
    random_state: int = 42,
) -> List[Dict[str, Any]]:
    """
    Run leave-one-class-out experiments for each attack family.
    
    Args:
        data_dir: Path to CIC-IDS2017 raw CSV files
        attack_families: List of attack family names to hold out (one at a time)
        target_column: Target column name
        split_mode: "chrono" or "random"
        contamination: Contamination parameter for Isolation Forest
        random_state: Random seed
        
    Returns:
        List of LOCO results for each held-out attack family
    """
    from backend.ml.preprocessing import preprocess_dataset
    from backend.ml.training import prepare_multiclass_dataset
    from backend.ml.anomaly_detection import IsolationForestDetector, ZeroDayDetector, create_zero_day_detector
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.calibration import CalibratedClassifierCV
    from backend.ml.calibration import calibrate_model
    from backend.ml.training import prepare_multiclass_dataset
    
    results = []
    
    # Load and preprocess data once
    logger.info(f"Loading data from {data_dir}")
    df = preprocessing.preprocess_dataset(data_dir)
    
    # Get all attack families present in data
    all_attack_families = sorted([c for c in df['Attack Type'].unique() if c != 'BENIGN'])
    
    for held_out_family in attack_families:
        logger.info(f"\n{'='*60}")
        logger.info(f"LOCO Experiment: Holding out '{held_out_family}'")
        logger.info(f"{'='*60}")
        
        # Filter data: remove held-out attack family from training
        train_df = df[~((df['Attack Type'] == held_out_family) & (df['Attack Type'] != 'BENIGN'))].copy()
        test_df = df.copy()  # Keep all for testing
        
        logger.info(f"Training data: {len(train_df)} rows, Test data: {len(df)} rows")
        logger.info(f"Held-out class '{held_out_family}' train samples: {sum(df['Attack Type'] == held_out_family)}")
        
        # Prepare training data (without held-out attack)
        train_multiclass = prepare_multiclass_dataset(
            train_df, target_column="Attack Type", split_mode="chrono"
        )
        
        # Prepare test data (includes held-out class)
        test_multiclass = prepare_multiclass_dataset(
            df, target_column="Attack Type", split_mode="chrono"
        )
        
        # Train Isolation Forest on benign training data only
        logger.info("Training Isolation Forest on benign training data...")
        benign_train_mask = (train_multiclass.y_train == "BENIGN")
        X_benign_train = train_multiclass.X_train[benign_train_mask]
        
        iso_forest = IsolationForestDetector(n_estimators=200, contamination=0.01, random_state=42)
        iso_forest.fit(X_benign_train, feature_names=None)
        
        # Train supervised model (Random Forest with class_weight='balanced')
        rf = RandomForestClassifier(n_estimators=200, class_weight='balanced', random_state=42, n_jobs=-1)
        rf.fit(multiclass_dataset.X_train, multiclass_dataset.y_train)
        
        # Calibrate probabilities
        calibrated_rf = CalibratedClassifierCV(rf, method='isotonic', cv=3)
        calibrated_rf.fit(X_train, y_train)
        
        # Create ZeroDayDetector
        zero_day_detector = ZeroDayDetector(
            supervised_model=calibrated_rf,
            anomaly_detector=iso_forest,
            t_conf=0.5,  # Will be calibrated later
            t_anom=0.5,
        )
        
        # Calibrate thresholds on benign validation data
        logger.info("Calibrating thresholds on benign validation data...")
        X_benign_val = X_test[y_test == "BENIGN"]
        y_benign = pd.Series(["BENIGN"] * len(X_test[y_test == "BENIGN"]))
        # We'd need benign test data for calibration
        
        # For now, use default thresholds
        zero_day_detector.t_conf = 0.5
        zero_day_detector.t_anom = 0.5
        
        # Evaluate on test set
        X_test_combined = test_multiclass.X_test
        y_test_combined = test_multiclass.y_test
        
        # Predictions
        results = zero_day_detector.predict(multiclass_dataset.X_test)
        
        # Compute metrics
        from sklearn.metrics import precision_recall_fscore_support, confusion_matrix
        
        y_true = test_multiclass.y_test
        y_pred = [r.predicted_class for r in results]
        y_zero_day = [r.is_zero_day for r in results]
        
        # Metrics on held-out class
        held_out_mask = (test_multiclass.y_test == held_out_family)
        benign_mask = (test_multiclass.y_test == "BENIGN")
        
        # Held-out class recall
        held_out_recall = np.mean([r.is_zero_day for i, r in enumerate(results) 
                                  if test_multiclass.y_test.iloc[i] == held_out_family])
        
        # Benign FPR
        benign_preds = [r.is_zero_day for i, r in enumerate(results) if test_multiclass.y_test.iloc[i] == "BENIGN"]
        benign_fpr = np.mean(benign_preds)
        
        # Held-out precision
        held_out_preds = [r.is_zero_day for i, r in enumerate(results) if test_multiclass.y_test.iloc[i] == held_out_family]
        held_out_precision = np.mean(held_out_preds) if held_out_preds else 0.0
        
        # Held-out F1
        from sklearn.metrics import f1_score
        y_true_held_out = [1 if test_multiclass.y_test.iloc[i] == held_out_family else 0 for i in range(len(results))]
        y_pred_held_out = [r.is_zero_day for r in results]
        held_out_f1 = f1_score(y_true_held_out, y_pred_held_out)
        held_out_precision = precision_score(y_true_held_out, y_pred_held_out)
        held_out_recall = recall_score(y_true_held_out, y_pred_held_out)
        
        # Benign FPR
        benign_fpr = np.mean([r.is_zero_day for i, r in enumerate(results) if test_multiclass.y_test.iloc[i] == "BENIGN"])
        
        # Calibrated thresholds
        t_conf = 0.5  # Would be calibrated
        t_anom = 0.5
        
        result = {
            "held_out_class": held_out_family,
            "train_samples": len(train_multiclass.X_train),
            "train_classes": len(np.unique(train_multiclass.y_train)),
            "test_samples": len(test_multiclass.X_test),
            "held_out_test_samples": int(held_out_mask.sum()),
            "benign_test_samples": int(benign_mask.sum()),
            "held_out_recall": held_out_recall,
            "benign_fpr": benign_fpr,
            "held_out_precision": held_out_precision,
            "held_out_f1": held_out_f1,
            "zero_day_recall": held_out_recall,  # Same as held_out_recall for zero-day
            "zero_day_precision": held_out_precision,
            "zero_day_f1": held_out_f1,
            "benign_fpr": benign_fpr,
            "t_conf": 0.5,
            "t_anom": 0.5,
            "train_time_seconds": 0.0,
            "test_time_seconds": 0.0,
        }
        
        logger.info(f"LOCO Results for {held_out_family}: "
                    f"held_out_recall={result['held_out_recall']:.3f}, "
                    f"benign_fpr={result['benign_fpr']:.4f}, "
                    f"held_out_f1={result['held_out_f1']:.3f}")
        
        results.append(result)
    
    return results


def save_loco_results(results: List[Dict[str, Any]], output_path: str = "results/loco_results.csv"):
    """Save LOCO results to CSV."""
    import os
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df = pd.DataFrame(results)
    df.to_csv(output_path, index=False)
    logger.info(f"Saved LOCO results to {output_path}")


def run_loco_pipeline(data_dir: str, output_dir: str = "results"):
    """
    Run complete LOCO pipeline and save results.
    
    Args:
        data_dir: Path to CIC-IDS2017 raw CSV files
        output_dir: Directory to save results
    """
    import os
    os.makedirs(output_dir, exist_ok=True)
    
    results = run_loco_experiment(data_dir)
    save_loco_results(results, os.path.join(output_dir, "loco_results.csv"))
    
    # Print summary
    df = pd.DataFrame(results)
    print("\n=== LOCO Experiment Summary ===")
    print(df[["held_out_class", "held_out_recall", "benign_fpr", "held_out_f1", "benign_fpr"]].to_string(index=False))
    
    return results