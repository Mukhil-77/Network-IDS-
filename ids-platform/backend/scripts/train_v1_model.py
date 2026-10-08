#!/usr/bin/env python
"""
Train Multi-Class IDS Model for NF-UQ-NIDS-v2 Dataset

Enhanced pipeline: Raw Features -> Imputer -> LabelEncoder (categorical) -> MinMaxScaler -> LightGBM
with SMOTE balancing for rare classes and enhanced feature engineering.
"""

import json
import warnings
import sklearn
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd
import joblib
from sklearn.preprocessing import LabelEncoder, MinMaxScaler
from sklearn.impute import SimpleImputer
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score, f1_score, precision_score, recall_score
from sklearn.utils.class_weight import compute_class_weight

# Import shared encoder class
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from backend.ml.encoders import LabelEncoderExt
from backend.ml.constants import PROJECT_VERSION
from backend.ml.artifacts import next_version_dir

# LightGBM
import lightgbm as lgb

# SMOTE for class balancing
from imblearn.over_sampling import SMOTE

warnings.filterwarnings('ignore')

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DATA_PATH = Path("data/raw/NF-UQ-NIDS-v2/NF-UQ-NIDS-v2.csv")

# MODEL_DIR will be created by next_version_dir() in train_model()
# This allows each training run to get a new version directory

# Columns to drop (not useful for detection)
DROP_COLS = ['IPV4_SRC_ADDR', 'IPV4_DST_ADDR', 'Dataset', 'Label', 'Attack']

# Categorical columns that need encoding
CAT_COLS = ['L4_SRC_PORT', 'L4_DST_PORT', 'PROTOCOL', 'L7_PROTO', 'TCP_FLAGS',
            'CLIENT_TCP_FLAGS', 'SERVER_TCP_FLAGS', 'ICMP_TYPE', 'ICMP_IPV4_TYPE',
            'DNS_QUERY_ID', 'DNS_QUERY_TYPE', 'DNS_TTL_ANSWER', 'FTP_COMMAND_RET_CODE']

# Sample size for training (use subset for faster training, set to None for full)
SAMPLE_SIZE = 2_000_000  # 2M rows for reasonable training time
RANDOM_STATE = 42
TEST_SIZE = 0.2

# SMOTE configuration - only oversample minority classes (those with < 1000 samples)
SMOTE_MIN_SAMPLES = 1000
SMOTE_K_NEIGHBORS = 5

# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------
def compute_sample_weights(y_train):
    """Compute per-sample weights for LightGBM to handle class imbalance."""
    class_weights = compute_class_weight('balanced', classes=np.unique(y_train), y=y_train)
    weight_dict = dict(zip(np.unique(y_train), class_weights))
    sample_weights = np.array([weight_dict[c] for c in y_train])
    return sample_weights


def apply_smote_balancing(X_train, y_train, min_samples=SMOTE_MIN_SAMPLES, k_neighbors=SMOTE_K_NEIGHBORS):
    """Apply SMOTE only to minority classes below min_samples threshold."""
    print("Checking class distribution for SMOTE...")
    
    # Count samples per class
    class_counts = pd.Series(y_train).value_counts()
    minority_classes = class_counts[class_counts < min_samples].index.tolist()
    
    if not minority_classes:
        print("No minority classes below threshold, skipping SMOTE")
        return X_train, y_train
    
    print(f"Minority classes for SMOTE: {minority_classes}")
    print(f"Class counts before SMOTE:\n{class_counts}")
    
    # Build sampling strategy - only oversample minority classes
    sampling_strategy = {cls: min_samples for cls in minority_classes}
    
    # Adjust k_neighbors for very small classes
    min_class_size = class_counts[minority_classes].min()
    effective_k = min(k_neighbors, min_class_size - 1) if min_class_size > 1 else 1
    
    smote = SMOTE(
        sampling_strategy=sampling_strategy,
        k_neighbors=effective_k,
        random_state=RANDOM_STATE,
    )
    
    print(f"Applying SMOTE (k_neighbors={effective_k})...")
    X_resampled, y_resampled = smote.fit_resample(X_train, y_train)
    
    new_counts = pd.Series(y_resampled).value_counts()
    print(f"Class counts after SMOTE:\n{new_counts}")
    print(f"Total samples: {len(X_train):,} -> {len(X_resampled):,}")
    
    return X_resampled, y_resampled


def load_and_prepare_data():
    """Load dataset and prepare for training."""
    print(f"Loading data from {DATA_PATH}...")
    
    # Read in chunks to handle large file
    chunks = pd.read_csv(DATA_PATH, chunksize=500_000)
    dfs = []
    total_rows = 0
    
    for chunk in chunks:
        dfs.append(chunk)
        total_rows += len(chunk)
        if SAMPLE_SIZE and total_rows >= SAMPLE_SIZE:
            break
    
    df = pd.concat(dfs, ignore_index=True)
    if SAMPLE_SIZE:
        df = df.sample(n=min(SAMPLE_SIZE, len(df)), random_state=RANDOM_STATE)
    
    print(f"Loaded {len(df):,} rows")
    print(f"Attack distribution:\n{df['Attack'].value_counts()}")
    
    # Separate features and target
    X = df.drop(DROP_COLS, axis=1)
    y = df['Attack']
    
    return X, y


def encode_categorical(X_train, X_test):
    """Encode categorical columns with LabelEncoderExt."""
    encoders = {}
    
    for col in CAT_COLS:
        if col in X_train.columns:
            le = LabelEncoderExt()
            X_train[col] = le.fit_transform(X_train[col])
            X_test[col] = le.transform(X_test[col])
            encoders[col] = le
    
    return X_train, X_test, encoders


def train_model():
    """Main training pipeline."""
    # Create new version directory
    MODEL_DIR = next_version_dir()
    print(f"Created model version directory: {MODEL_DIR}")
    
    print("=" * 60)
    print("Training Multi-Class IDS Model (LightGBM + SMOTE)")
    print("=" * 60)
    
    # 1. Load data
    X, y = load_and_prepare_data()
    
    # 2. Split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=TEST_SIZE, random_state=RANDOM_STATE, stratify=y
    )
    print(f"\nTrain: {len(X_train):,}, Test: {len(X_test):,}")
    
    # 3. Encode categorical
    print("Encoding categorical features...")
    X_train, X_test, cat_encoders = encode_categorical(X_train, X_test)
    
    # 4. Impute missing values
    print("Imputing missing values...")
    imputer = SimpleImputer(strategy='mean')
    X_train_imp = pd.DataFrame(imputer.fit_transform(X_train), columns=X_train.columns)
    X_test_imp = pd.DataFrame(imputer.transform(X_test), columns=X_test.columns)
    
    # 5. Scale features
    print("Scaling features with MinMaxScaler...")
    scaler = MinMaxScaler()
    X_train_scaled = pd.DataFrame(scaler.fit_transform(X_train_imp), columns=X_train.columns)
    X_test_scaled = pd.DataFrame(scaler.transform(X_test_imp), columns=X_test.columns)
    
    # 6. Encode target labels
    print("Encoding target labels...")
    target_encoder = LabelEncoder()
    y_train_enc = target_encoder.fit_transform(y_train)
    y_test_enc = target_encoder.transform(y_test)
    
    attack_labels = list(target_encoder.classes_)
    print(f"Classes ({len(attack_labels)}): {attack_labels}")
    
    # 7. Apply SMOTE balancing for rare classes
    print("\nApplying class balancing...")
    X_train_balanced, y_train_balanced = apply_smote_balancing(X_train_scaled, y_train_enc)
    
    # 8. Compute sample weights for LightGBM
    sample_weights = compute_sample_weights(y_train_balanced)
    
    # 9. Train LightGBM
    print("\nTraining LightGBMClassifier...")
    lgbm = lgb.LGBMClassifier(
        n_estimators=300,
        max_depth=12,
        num_leaves=63,
        learning_rate=0.05,
        min_child_samples=20,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_alpha=0.1,
        reg_lambda=0.1,
        n_jobs=-1,
        random_state=RANDOM_STATE,
        verbosity=-1,
        class_weight='balanced',
        force_col_wise=True,
    )
    
    # Train with sample weights (no early stopping - let it train fully)
    lgbm.fit(
        X_train_balanced, y_train_balanced,
        sample_weight=sample_weights,
        eval_set=[(X_test_scaled, y_test_enc)],
        eval_metric='multi_logloss',
        callbacks=[lgb.log_evaluation(50)]
    )
    
    # 10. Evaluate
    print("\nEvaluating...")
    y_pred = lgbm.predict(X_test_scaled)
    
    acc = accuracy_score(y_test_enc, y_pred)
    f1_macro = f1_score(y_test_enc, y_pred, average='macro')
    f1_weighted = f1_score(y_test_enc, y_pred, average='weighted')
    precision_macro = precision_score(y_test_enc, y_pred, average='macro', zero_division=0)
    recall_macro = recall_score(y_test_enc, y_pred, average='macro', zero_division=0)
    
    print(f"Accuracy: {acc:.4f}")
    print(f"Precision (macro): {precision_macro:.4f}")
    print(f"Recall (macro): {recall_macro:.4f}")
    print(f"F1 Macro: {f1_macro:.4f}")
    print(f"F1 Weighted: {f1_weighted:.4f}")
    print("\nClassification Report:")
    print(classification_report(y_test_enc, y_pred, target_names=attack_labels))
    
    # 11. Feature importance (LightGBM gain-based)
    feature_imp = pd.DataFrame({
        'feature': X_train.columns,
        'importance': lgbm.feature_importances_
    }).sort_values('importance', ascending=False)
    
    print("\nTop 20 Features (Gain-based):")
    print(feature_imp.head(20).to_string(index=False))
    
    # 12. Save artifacts
    print(f"\nSaving artifacts to {MODEL_DIR}...")
    
    joblib.dump(lgbm, MODEL_DIR / "lgbm_model.pkl")
    joblib.dump(scaler, MODEL_DIR / "scaler.pkl")
    joblib.dump(imputer, MODEL_DIR / "imputer.pkl")
    joblib.dump(target_encoder, MODEL_DIR / "label_encoder.pkl")
    joblib.dump(cat_encoders, MODEL_DIR / "cat_encoders.pkl")
    
    # Also save as generic model.pkl for artifacts.py compatibility
    joblib.dump(lgbm, MODEL_DIR / "model.pkl")
    
    # Save feature names
    feature_names = list(X_train.columns)
    with open(MODEL_DIR / "feature_names.json", 'w') as f:
        json.dump(feature_names, f)
    
    # Save metadata
    version_name = MODEL_DIR.name  # e.g., "v3"
    metadata = {
        "model_name": f"lightgbm_nids_{version_name}",
        "dataset": "NF-UQ-NIDS-v2",
        "training_date": datetime.now().isoformat(),
        "accuracy": float(acc),
        "precision": float(precision_macro),
        "recall": float(recall_macro),
        "f1_score": float(f1_macro),
        "f1_weighted": float(f1_weighted),
        "features": feature_names,
        "pca_components": 0,
        "sklearn_version": sklearn.__version__,
        "lightgbm_version": lgb.__version__,
        "project_version": PROJECT_VERSION,
        "n_classes": len(attack_labels),
        "classes": attack_labels,
        "n_features": len(feature_names),
        "feature_names": feature_names,
        "categorical_columns": CAT_COLS,
        "drop_columns": DROP_COLS,
        "sample_size": SAMPLE_SIZE,
        "test_size": TEST_SIZE,
        "random_state": RANDOM_STATE,
        "smote_min_samples": SMOTE_MIN_SAMPLES,
        "smote_k_neighbors": SMOTE_K_NEIGHBORS,
        "model_params": lgbm.get_params(),
        "severity_mapping": {
            "Benign": "LOW",
            "DDoS": "CRITICAL",
            "DoS": "CRITICAL",
            "scanning": "MEDIUM",
            "Reconnaissance": "LOW",
            "xss": "HIGH",
            "password": "HIGH",
            "injection": "HIGH",
            "Bot": "CRITICAL",
            "Brute Force": "HIGH",
            "Infilteration": "CRITICAL",
            "Exploits": "CRITICAL",
            "Fuzzers": "MEDIUM",
            "Backdoor": "CRITICAL",
            "Generic": "MEDIUM",
            "mitm": "HIGH",
            "ransomware": "CRITICAL",
            "Theft": "HIGH",
            "Analysis": "LOW",
            "Shellcode": "CRITICAL",
            "Worms": "CRITICAL"
        }
    }
    
    with open(MODEL_DIR / "metadata.json", 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print("Training complete!")
    print(f"Model saved to: {MODEL_DIR}")
    
    return metadata


if __name__ == "__main__":
    train_model()