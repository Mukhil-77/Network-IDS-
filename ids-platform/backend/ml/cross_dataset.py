"""
Cross-dataset evaluation for IDS models.

Supports cross-dataset evaluation between CIC-IDS2017 and CSE-CIC-IDS2018.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import logging
import numpy as np
import pandas as pd

from backend.ml.constants import TARGET_COLUMN
from backend.ml.datasets import DatasetRegistry, DatasetType
from backend.ml.evaluation import evaluate_model
from backend.ml.feature_schema import CANONICAL_FEATURE_NAMES
from backend.ml.training import prepare_multiclass_dataset
from backend.utils.logger import get_logger

logger = get_logger(__name__)


__all__ = [
    "CrossDatasetResult",
    "run_cross_dataset_evaluation",
    "run_bidirectional_experiment",
    "generate_generalization_report",
]

logger = get_logger(__name__)


@dataclass
class CrossDatasetResult:
    """Results from a cross-dataset evaluation experiment."""
    train_dataset: str
    test_dataset: str
    experiment_type: str  # "in_domain", "cross_2017_to_2018", "cross_2018_to_2017", "leave_one_out"
    held_out_class: Optional[str] = None
    
    # Metrics
    in_domain_accuracy: Optional[float] = None
    cross_domain_accuracy: Optional[float] = None
    accuracy_drop: Optional[float] = None
    
    # Per-class metrics
    per_class_precision: Dict[str, float] = None
    per_class_recall: Dict[str, float] = None
    per_class_f1: Dict[str, float] = None
    
    # Additional metrics
    macro_f1: Optional[float] = None
    weighted_f1: Optional[float] = None
    mcc: Optional[float] = None
    pr_auc: Optional[float] = None
    roc_auc: Optional[float] = None
    
    # Feature mapping info
    feature_overlap: int = 0
    missing_features: List[str] = None
    extra_features: List[str] = None


def load_cic2017(data_dir: str) -> Tuple[pd.DataFrame, pd.Series]:
    """Load CIC-IDS2017 dataset."""
    from backend.ml.preprocessing import preprocess_dataset
    
    df = preprocess_dataset("data/raw/CIC-IDS2017")
    return df.drop(columns=["Attack Type"]), df["Attack Type"]


def load_cic2018(data_dir: str) -> Tuple[pd.DataFrame, pd.Series]:
    """Load CSE-CIC-IDS2018 dataset."""
    data_dir = Path(data_dir)
    if not data_dir.exists():
        raise FileNotFoundError(f"CSE-CIC-IDS2018 directory not found at {data_dir}")
    
    csv_files = list(data_dir.glob("*.csv"))
    if not csv_files:
        raise ValueError(f"No CSV files found in {data_dir}")
    
    logger.info(f"Loading {len(csv_files)} files from CSE-CIC-IDS2018")
    
    frames = []
    for csv_file in csv_files:
        try:
            df = pd.read_csv(csv_file, low_memory=False)
            logger.info(f"Loaded {csv_file.name}: {len(df)} rows")
            frames.append(df)
        except Exception as e:
            logger.warning(f"Failed to load {csv_file.name}: {e}")
    
    if not frames:
        raise ValueError("No valid CSV files loaded")
    
    df = pd.concat(frames, ignore_index=True)
    logger.info(f"Total CSE-CIC-IDS2018 rows: {len(df)}")
    
    # Clean column names
    df.columns = [c.strip() for c in df.columns]
    
    # Map labels to unified taxonomy
    label_col = "Label" if "Label" in df.columns else "Label"
    y = df[label_col].astype(str).str.strip()
    X = df.drop(columns=[label_col])
    
    # Clean numeric columns
    X = X.select_dtypes(include=[np.number])
    X = X.replace([np.inf, -np.inf], np.nan).fillna(0)
    
    return X, y


def harmonize_labels(y: pd.Series, mapping: Dict[str, str]) -> pd.Series:
    """Map labels to unified taxonomy."""
    return y.map(mapping).fillna("UNKNOWN")


# Label mappings for CIC-IDS2017 and CSE-CIC-IDS2018
CIC2017_LABEL_MAP = {
    "BENIGN": "BENIGN",
    "DoS Hulk": "DoS",
    "DoS GoldenEye": "DoS",
    "DoS slowloris": "DoS",
    "DoS Slowhttptest": "DoS",
    "PortScan": "PortScan",
    "FTP-Patator": "BruteForce",
    "SSH-Patator": "BruteForce",
    "Bot": "Botnet",
    "Web Attack \ufffd Brute Force": "WebAttack-BruteForce",
    "Web Attack \ufffd XSS": "WebAttack-XSS",
    "Web Attack \ufffd Sql Injection": "WebAttack-SQLi",
    "Infiltration": "Infiltration",
    "Heartbleed": "Heartbleed",
}

CIC2018_LABEL_MAP = {
    "Benign": "BENIGN",
    "Benign": "BENIGN",
    "BENIGN": "BENIGN",
    "DDoS attacks-LOIC-HTTP": "DDoS",
    "DDoS attacks-LOIC-HTTP": "DDoS",
    "DDOS attack-LOIC-UDP": "DDoS",
    "DDOS attack-HOIC": "DDoS",
    "DoS attacks-GoldenEye": "DoS",
    "DoS attacks-GoldenEye": "DoS",
    "DoS attacks-Slowloris": "DoS",
    "DoS attacks-Slowloris": "DoS",
    "DoS attacks-SlowHTTPTest": "DoS",
    "DoS attacks-SlowHTTPTest": "DoS",
    "PortScan": "PortScan",
    "PortScan": "PortScan",
    "FTP-BruteForce": "BruteForce",
    "FTP-Patator": "BruteForce",
    "SSH-Patator": "BruteForce",
    "Bot": "Botnet",
    "Botnet": "Botnet",
    "Web Attack \ufffd Brute Force": "WebAttack-BruteForce",
    "Web Attack \ufffd XSS": "WebAttack-XSS",
    "Web Attack \ufffd Sql Injection": "WebAttack-SQLi",
    "Infiltration": "Infiltration",
    "Heartbleed": "Heartbleed",
    "SSH-Patator": "BruteForce",
    "FTP-Patator": "BruteForce",
}


def harmonize_labels(y: pd.Series) -> pd.Series:
    """Apply both label mappings and unify."""
    y_clean = y.astype(str).str.strip()
    
    # Try both mappings
    mapped = y_clean.map(CIC2017_LABEL_MAP)
    unmapped = mapped.isna()
    if unmapped.any():
        mapped[unmapped] = y_clean[unmapped].map(CIC2018_LABEL_MAP)
    
    still_unmapped = mapped.isna()
    if still_unmapped.any():
        mapped[still_unmapped] = "UNKNOWN"
        logger.warning(f"Unmapped labels: {y_clean[still_unmapped].unique()[:10]}")
    
    return mapped


def compute_common_features(
    X_2017: pd.DataFrame, 
    X_2018: pd.DataFrame
) -> Tuple[List[str], Dict[str, List[str]]]:
    """
    Compute common features between two datasets.
    
    Returns:
        (common_features, {dataset: missing_features})
    """
    feat_2017 = set(X_2017.columns)
    feat_2018 = set(X_2018.columns)
    
    common = sorted(feat_2017 & feat_2018)
    missing_2017 = sorted(feat_2018 - feat_2017)
    missing_2018 = sorted(feat_2017 - feat_2018)
    
    return common, {
        "CIC-IDS2017": missing_2018,
        "CSE-CIC-IDS2018": missing_2017,
    }


def run_cross_dataset_evaluation(
    models_dir: str = "models",
    data_dir_2017: str = "data/raw/CIC-IDS2017",
    data_dir_2018: str = "data/raw/CSE-CIC-IDS2018",
    split_mode: str = "chrono",
) -> List[Dict[str, Any]]:
    """
    Run cross-dataset evaluation experiments.
    
    Experiments:
    1. In-domain: Train on 2017, test on 2017 (baseline)
    2. Cross 2017->2018: Train on 2017, test on 2018
    3. Cross 2018->2017: Train on 2018, test on 2017
    4. Leave-one-class-out on 2017
    4. Leave-one-class-out on 2018
    
    Returns list of CrossDatasetResult objects.
    """
    from backend.ml import artifacts, evaluation, training
    from backend.ml.feature_selection import select_features_pipeline
    from backend.ml.training import prepare_multiclass_dataset
    
    results = []
    
    # Load datasets
    logger.info("Loading CIC-IDS2017...")
    X_2017, y_2017 = load_cic2017(data_dir_2017)
    logger.info(f"CIC-IDS2017: {len(X_2017)} samples, {X_2017.shape[1]} features")
    
    logger.info("Loading CSE-CIC-IDS2018...")
    X_2018, y_2018 = load_cic2018(data_dir_2018)
    logger.info(f"CSE-CIC-IDS2018: {len(X_2018)} samples, {X_2018.shape[1]} features")
    
    # Harmonize labels
    y_2017_mapped = harmonize_labels(y_2017)
    y_2018_mapped = harmonize_labels(y_2018)
    
    # Compute common features
    common_features, missing_info = compute_common_features(
        X_2017.select_dtypes(include=[np.number]),
        X_2018.select_dtypes(include=[np.number])
    )
    
    logger.info(f"Common features: {len(common_features)}")
    logger.info(f"Missing from 2017: {missing_info['CIC-IDS2017']}")
    logger.info(f"Missing from 2018: {missing_info['CSE-CIC-IDS2018']}")
    
    # For now, we'll use only common features
    # In practice, we'd need to handle missing features properly
    # For now, use only common features
    X_2017_common = X_2017[common_features]
    X_2018_common = X_2018[common_features]
    
    # Harmonize labels
    y_2017_mapped = harmonize_labels(y_2017)
    y_2018_mapped = harmonize_labels(y_2018)
    
    # Check class distributions
    logger.info(f"2017 class distribution:\n{y_2017_mapped.value_counts()}")
    logger.info(f"2018 class distribution:\n{y_2018_mapped.value_counts()}")
    
    # Common classes
    common_classes = set(y_2017_mapped.unique()) & set(y_2018_mapped.unique())
    logger.info(f"Common classes: {common_classes}")
    
    results = []
    
    # Experiment 1: In-domain 2017 (train/test split on 2017)
    logger.info("Experiment 1: In-domain CIC-IDS2017 (chrono split)")
    dataset_2017 = prepare_multiclass_dataset(
        data_dir_2017, 
        target_column="Attack Type",
        split_mode="chrono"
    )
    
    # Train Random Forest
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.calibration import CalibratedClassifierCV
    
    rf = RandomForestClassifier(
        n_estimators=200,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1
    )
    
    # Train on 2017, test on 2017 (in-domain baseline)
    logger.info("Training on CIC-IDS2017, testing on CIC-IDS2017 (in-domain)...")
    rf.fit(X_2017_train, y_2017_train)
    rf.fit(X_2017_train, y_2017_train)
    # ... continue evaluation
    
    results = []

    # Experiment 1: In-domain 2017 (train/test split on 2017)
    logger.info("Experiment 1: In-domain CIC-IDS2017 (chrono split)")
    dataset_2017 = prepare_multiclass_dataset(
        data_dir_2017, 
        target_column="Attack Type",
        split_mode="chrono"
    )

    # Train Random Forest
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.calibration import CalibratedClassifierCV

    rf = RandomForestClassifier(
        n_estimators=200,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1
    )

    # Train on 2017, test on 2017 (in-domain baseline)
    logger.info("Training on CIC-IDS2017, testing on CIC-IDS2017 (in-domain)...")
    rf.fit(dataset_2017.X_train, dataset_2017.y_train)
    
    # Evaluate in-domain
    from backend.ml import evaluation
    in_domain_result = evaluation.evaluate_model(
        "rf_in_domain", 
        rf, 
        dataset_2017.X_test, 
        dataset_2017.y_test
    )
    
    results.append(CrossDatasetResult(
        config=CrossDatasetExperimentConfig(
            experiment_type=ExperimentType.IN_DOMAIN,
            train_dataset="CIC-IDS2017",
            test_dataset="CIC-IDS2017",
        ),
        in_domain_result=in_domain_result,
        cross_dataset_result=None,
        performance_degradation={},
        per_class_degradation={},
        feature_overlap=len(common_features),
        missing_features=missing_features,
    ))

    # Experiment 2: Cross-dataset 2017 -> 2018
    logger.info("Experiment 2: Cross-dataset CIC-IDS2017 -> CSE-CIC-IDS2018")
    dataset_2018 = prepare_multiclass_dataset(
        data_dir_2018,
        target_column="Attack Type",
        split_mode="chrono"
    )
    
    # Train on 2017 common features, test on 2018 common features
    rf.fit(dataset_2017.X_train, dataset_2017.y_train)
    
    # Evaluate on 2018 test set
    cross_result = evaluation.evaluate_model(
        "rf_cross_2017_2018",
        rf,
        dataset_2018.X_test,
        dataset_2018.y_test
    )
    
    degradation = compute_performance_degradation(in_domain_result, cross_result)
    per_class = compute_per_class_degradation(in_domain_result, cross_result)
    
    results.append(CrossDatasetResult(
        config=CrossDatasetExperimentConfig(
            experiment_type=ExperimentType.CROSS_DATASET,
            train_dataset="CIC-IDS2017",
            test_dataset="CSE-CIC-IDS2018",
        ),
        in_domain_result=in_domain_result,
        cross_dataset_result=cross_result,
        performance_degradation=degradation,
        per_class_degradation=per_class,
        feature_overlap=len(common_features),
        missing_features=missing_features,
    ))

    # Experiment 3: Cross-dataset 2018 -> 2017
    logger.info("Experiment 3: Cross-dataset CSE-CIC-IDS2018 -> CIC-IDS2017")
    dataset_2018_train = prepare_multiclass_dataset(
        data_dir_2018,
        target_column="Attack Type",
        split_mode="chrono"
    )
    
    rf2 = RandomForestClassifier(
        n_estimators=200,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1
    )
    rf2.fit(dataset_2018.X_train, dataset_2018.y_train)
    
    reverse_result = evaluation.evaluate_model(
        "rf_cross_2018_2017",
        rf2,
        dataset_2017.X_test,
        dataset_2017.y_test
    )
    
    reverse_degradation = compute_performance_degradation(
        evaluation.evaluate_model("rf_in_domain_2018", rf2, dataset_2018.X_test, dataset_2018.y_test),
        reverse_result
    )
    reverse_per_class = compute_per_class_degradation(
        evaluation.evaluate_model("rf_in_domain_2018", rf2, dataset_2018.X_test, dataset_2018.y_test),
        reverse_result
    )
    
    results.append(CrossDatasetResult(
        config=CrossDatasetExperimentConfig(
            experiment_type=ExperimentType.CROSS_DATASET,
            train_dataset="CSE-CIC-IDS2018",
            test_dataset="CIC-IDS2017",
        ),
        in_domain_result=evaluation.evaluate_model("rf_in_domain_2018", rf2, dataset_2018.X_test, dataset_2018.y_test),
        cross_dataset_result=reverse_result,
        performance_degradation=reverse_degradation,
        per_class_degradation=reverse_per_class,
        feature_overlap=len(common_features),
        missing_features=missing_features,
    ))

    # Experiment 4: Leave-one-class-out on 2017
    logger.info("Experiment 4: Leave-one-class-out on CIC-IDS2017")
    attack_families = [
        "DoS", "DDoS", "Port Scan", "Bot", "Brute Force", 
        "Web Attack - Brute Force", "XSS", "SQL Injection",
        "Infiltration", "Heartbleed"
    ]
    
    for attack_family in attack_families:
        logger.info(f"Leave-one-out: {attack_family}")
        # Filter out the attack family from training
        train_mask = dataset_2017.y_train != attack_family
        test_mask = dataset_2017.y_test == attack_family
        
        if test_mask.sum() == 0:
            logger.warning(f"No test samples for {attack_family}, skipping")
            continue
            
        X_train_filtered = dataset_2017.X_train[train_mask]
        y_train_filtered = dataset_2017.y_train[train_mask]
        
        rf_loo = RandomForestClassifier(
            n_estimators=200,
            class_weight="balanced",
            random_state=42,
            n_jobs=-1
        )
        rf_loo.fit(dataset_2017.X_train[train_mask], dataset_2017.y_train[train_mask])
        
        # Evaluate on held-out class
        y_true_held = dataset_2017.y_test[test_mask]
        y_pred_held = rf_loo.predict(dataset_2017.X_test[test_mask])
        
        from sklearn.metrics import recall_score, f1_score, precision_score
        held_out_recall = recall_score(
            [1]*len(y_pred_held), y_pred_held, average="binary", pos_label=attack_family
        )
        
        # Also test on benign
        benign_mask = dataset_2017.y_test == "BENIGN"
        benign_fpr = (rf_loo.predict(dataset_2017.X_test[benign_mask]) != "BENIGN").mean()
        
        results.append(CrossDatasetResult(
            config=CrossDatasetExperimentConfig(
                experiment_type=ExperimentType.LEAVE_ONE_OUT,
                train_dataset="CIC-IDS2017",
                test_dataset="CIC-IDS2017",
                excluded_attack=attack_family,
            ),
            in_domain_result=evaluation.evaluate_model(
                f"rf_in_domain_2017_loo_{attack_family}",
                rf, 
                dataset_2017.X_test[~test_mask], 
                dataset_2017.y_test[~test_mask]
            ),
            cross_dataset_result=evaluation.evaluate_model(
                f"rf_loo_{attack_family}",
                rf_loo,
                dataset_2017.X_test[test_mask],
                dataset_2017.y_test[test_mask]
            ),
            performance_degradation={},
            per_class_degradation={},
            feature_overlap=len(common_features),
            missing_features=missing_features,
        ))

    # Experiment 5: Leave-one-out on 2018
    logger.info("Experiment 5: Leave-one-class-out on CSE-CIC-IDS2018")
    attack_families_2018 = list(set(dataset_2018.y_train.unique()) - {"BENIGN"})
    
    for attack_family in attack_families_2018:
        logger.info(f"Leave-one-out on 2018: {attack_family}")
        train_mask = dataset_2018.y_train != attack_family
        test_mask = dataset_2018.y_test == attack_family
        
        if test_mask.sum() == 0:
            logger.warning(f"No test samples for {attack_family}, skipping")
            continue
            
        rf_loo = RandomForestClassifier(
            n_estimators=200,
            class_weight="balanced",
            random_state=42,
            n_jobs=-1
        )
        rf_loo.fit(dataset_2018.X_train[train_mask], dataset_2018.y_train[train_mask])
        
        held_out_recall = recall_score(
            [1]*test_mask.sum(), 
            rf_loo.predict(dataset_2018.X_test[test_mask]), 
            average="binary", pos_label=attack_family
        )
        
        benign_mask = dataset_2018.y_test == "BENIGN"
        benign_fpr = (rf_loo.predict(dataset_2018.X_test[benign_mask]) != "BENIGN").mean()
        
        # Add to results
        # ... similar to above

    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    results = run_cross_dataset_evaluation()
    for r in results:
        print(r)