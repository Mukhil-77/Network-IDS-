"""
The trained ML model from final.ipynb, transplanted into the backend ML folder.

This module is the "trained model" part of final.ipynb, converted from the
notebook cell-for-cell into a runnable backend entry point. It ends with the
model the notebook itself ranked as the best multi-class model - Random
Forest Model 2 (rf2) - and saves the full trained bundle (model + scaler +
PCA + feature names + metadata) into a versioned models/vN directory in
exactly the format backend.ml.artifacts expects, so once this has run, the
API's /predict serves the notebook's actual trained model.

Notebook cells reproduced:

    cell 6   data = pd.concat(data_list, ignore_index=True)
    cell 14  data.drop_duplicates(inplace=True)
    cell 17  data.replace([np.inf, -np.inf], np.nan, inplace=True)
    cell 26  data['Flow Bytes/s'].fillna(med_flow_bytes, inplace=True)
             data['Flow Packets/s'].fillna(med_flow_packets, inplace=True)
    cell 28  downcast float64 -> float32, int64 -> int32 (memory)
    cell 32  attack_map -> data['Attack Type']
    cell 34  data.drop('Label', axis=1, inplace=True)
    cell 59  drop single-unique-value columns
    cell 62  scaler = StandardScaler(); scaled_features = scaler.fit_transform(features)
    cell 63  size = len(features.columns) // 2
             ipca = IncrementalPCA(n_components=size, batch_size=500)
             for batch in np.array_split(scaled_features, len(features) // 500):
                 ipca.partial_fit(batch)
    cell 64  transformed_features = ipca.transform(scaled_features)
             new_data = pd.DataFrame(transformed_features,
                                     columns=[f'PC{i+1}' for i in range(size)])
             new_data['Attack Type'] = attacks.values
    cell 77  keep classes with > 1950 rows; cap classes > 2500 rows at 5000
    cell 78  smote = SMOTE(sampling_strategy='auto', random_state=0)
    cell 79  X_train, X_test, y_train, y_test = train_test_split(
                 features, labels, test_size=0.25, random_state=0)
    cell 81  rf2 = RandomForestClassifier(n_estimators=15, max_depth=8,
                                          max_features=20, random_state=0)
             rf2.fit(X_train, y_train)

Usage:

    python -m backend.ml.notebook_model data/raw
    python -m backend.ml.notebook_model data/raw --models-dir models --force-version 2
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from imblearn.over_sampling import SMOTE
from sklearn.decomposition import IncrementalPCA
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.preprocessing import StandardScaler

from backend.ml import artifacts, evaluation
from backend.ml.constants import RAW_DATA_FILENAMES
from backend.utils.logger import get_logger

logger = get_logger(__name__)

# Notebook cell 32 - the exact attack_map used to train rf2. Web attacks are
# grouped into a single "Web Attack" class, exactly as the notebook did.
# The keyword fallback below exists because the raw CSVs carry a mojibake
# character ("\ufffd") in the web-attack labels that can vary by encoding.
NOTEBOOK_ATTACK_MAP = {
    "BENIGN": "BENIGN",
    "DDoS": "DDoS",
    "DoS Hulk": "DoS",
    "DoS GoldenEye": "DoS",
    "DoS slowloris": "DoS",
    "DoS Slowhttptest": "DoS",
    "PortScan": "Port Scan",
    "FTP-Patator": "Brute Force",
    "SSH-Patator": "Brute Force",
    "Bot": "Bot",
    "Infiltration": "Infiltration",
    "Heartbleed": "Heartbleed",
}

NOTEBOOK_ATTACK_KEYWORDS = {
    "web attack": "Web Attack",
    "brute force": "Brute Force",
}

ATTACK_TYPE_COLUMN = "Attack Type"
MODEL_NAME = "RandomForestClassifier (rf2)"
RF2_PARAMS = {"n_estimators": 15, "max_depth": 8, "max_features": 20, "random_state": 0}


# ==========================================================================
# Notebook cells 5-6: load the 8 daily CSVs and merge them
# ==========================================================================

def load_notebook_data(data_dir: str) -> pd.DataFrame:
    """Load the 8 CIC-IDS2017 CSVs in the notebook's order and concatenate them."""
    frames = []
    for filename in RAW_DATA_FILENAMES:
        df = pd.read_csv(Path(data_dir) / filename)
        logger.info("Loaded '%s' -> %d rows, %d columns", filename, *df.shape)
        frames.append(df)
    data = pd.concat(frames, ignore_index=True)
    # Notebook cell 13 - the raw CSVs have whitespace in some header names
    data.columns = [col.strip() for col in data.columns]
    logger.info("Merged dataset -> %d rows, %d columns", *data.shape)
    return data


# ==========================================================================
# Notebook cells 14-34: cleaning + label mapping
# ==========================================================================

def clean_notebook_data(data: pd.DataFrame) -> pd.DataFrame:
    """Notebook cells 14, 17, 26, 28, 32, 34: dedupe, inf -> NaN, median fill,
    downcast, map labels to Attack Type, drop the raw Label column."""
    data = data.copy()

    # Cell 14
    data.drop_duplicates(inplace=True)
    data.reset_index(drop=True, inplace=True)

    # Cell 17
    data.replace([np.inf, -np.inf], np.nan, inplace=True)

    # Cell 26 - the two columns the notebook found to have missing values.
    # Assignment form (not inplace) is required: with pandas 2.x Copy-on-Write,
    # an inplace fillna on a column silently does nothing.
    med_flow_bytes = data["Flow Bytes/s"].median()
    med_flow_packets = data["Flow Packets/s"].median()
    data["Flow Bytes/s"] = data["Flow Bytes/s"].fillna(med_flow_bytes)
    data["Flow Packets/s"] = data["Flow Packets/s"].fillna(med_flow_packets)

    # Cell 28 - downcast to halve memory usage
    for col in data.columns:
        if data[col].dtype == np.float64:
            data[col] = data[col].astype(np.float32)
        elif data[col].dtype == np.int64:
            data[col] = data[col].astype(np.int32)

    # Cell 32 (robust version of the notebook's attack_map)
    def _map_label(raw_label: str) -> str:
        raw_label = str(raw_label).strip()
        if raw_label in NOTEBOOK_ATTACK_MAP:
            return NOTEBOOK_ATTACK_MAP[raw_label]
        lowered = raw_label.lower()
        for keyword, mapped_type in NOTEBOOK_ATTACK_KEYWORDS.items():
            if keyword in lowered:
                return mapped_type
        return raw_label

    data[ATTACK_TYPE_COLUMN] = data["Label"].map(_map_label)

    # Cell 34
    data.drop("Label", axis=1, inplace=True)

    logger.info("Cleaned dataset -> %d rows, %d columns", *data.shape)
    logger.info("Attack Type distribution:\n%s", data[ATTACK_TYPE_COLUMN].value_counts().to_string())
    return data


# ==========================================================================
# Notebook cell 59: drop columns with only one unique value
# ==========================================================================

def drop_invariant_columns(data: pd.DataFrame) -> pd.DataFrame:
    num_unique = data.nunique()
    one_variable = num_unique[num_unique == 1]
    not_one_variable = num_unique[num_unique > 1].index

    dropped_cols = one_variable.index
    if len(dropped_cols):
        logger.info("Dropped invariant columns: %s", list(dropped_cols))
    return data[not_one_variable]


# ==========================================================================
# Notebook cells 62-64: StandardScaler + IncrementalPCA -> new_data
# ==========================================================================

def fit_scaler_and_pca(data: pd.DataFrame) -> tuple[StandardScaler, IncrementalPCA, pd.DataFrame]:
    """Cells 62-64: standardize, fit IncrementalPCA in 500-row batches, and
    build the PC1..PCn + Attack Type DataFrame the model trains on."""
    features = data.drop(ATTACK_TYPE_COLUMN, axis=1)
    attacks = data[ATTACK_TYPE_COLUMN]

    # Cell 62
    scaler = StandardScaler()
    scaled_features = scaler.fit_transform(features)

    # Cell 63
    size = len(features.columns) // 2
    ipca = IncrementalPCA(n_components=size, batch_size=500)
    for batch in np.array_split(scaled_features, len(features) // 500):
        ipca.partial_fit(batch)

    logger.info(
        "IncrementalPCA fitted: n_components=%d, information retained=%.2f%%",
        size,
        float(np.sum(ipca.explained_variance_ratio_)) * 100,
    )

    # Cell 64
    transformed_features = ipca.transform(scaled_features)
    new_data = pd.DataFrame(
        transformed_features, columns=[f"PC{i + 1}" for i in range(size)]
    )
    new_data[ATTACK_TYPE_COLUMN] = attacks.values

    del scaled_features, transformed_features
    return scaler, ipca, new_data


# ==========================================================================
# Notebook cells 77-79: multi-class balancing + train/test split
# ==========================================================================

def prepare_multiclass_dataset(new_data: pd.DataFrame):
    """Cells 77-79: keep classes with > 1950 rows, cap oversized classes at
    5000, SMOTE-balance, shuffle, then split 75/25 with random_state=0."""
    # Cell 77
    class_counts = new_data[ATTACK_TYPE_COLUMN].value_counts()
    selected_classes = class_counts[class_counts > 1950]
    class_names = selected_classes.index
    selected = new_data[new_data[ATTACK_TYPE_COLUMN].isin(class_names)]

    dfs = []
    for name in class_names:
        df = selected[selected[ATTACK_TYPE_COLUMN] == name]
        if len(df) > 2500:
            df = df.sample(n=5000, random_state=0)
        dfs.append(df)

    df = pd.concat(dfs, ignore_index=True)
    logger.info("Multi-class dataset before SMOTE:\n%s", df[ATTACK_TYPE_COLUMN].value_counts().to_string())

    # Cell 78
    X = df.drop(ATTACK_TYPE_COLUMN, axis=1)
    y = df[ATTACK_TYPE_COLUMN]

    smote = SMOTE(sampling_strategy="auto", random_state=0)
    X_upsampled, y_upsampled = smote.fit_resample(X, y)

    blnc_data = pd.DataFrame(X_upsampled)
    blnc_data[ATTACK_TYPE_COLUMN] = y_upsampled
    blnc_data = blnc_data.sample(frac=1)
    logger.info("Multi-class dataset after SMOTE:\n%s", blnc_data[ATTACK_TYPE_COLUMN].value_counts().to_string())

    # Cell 79
    features = blnc_data.drop(ATTACK_TYPE_COLUMN, axis=1)
    labels = blnc_data[ATTACK_TYPE_COLUMN]

    X_train, X_test, y_train, y_test = train_test_split(
        features, labels, test_size=0.25, random_state=0
    )
    return X_train, X_test, y_train, y_test


# ==========================================================================
# Notebook cell 81: train rf2 (Random Forest Model 2)
# ==========================================================================

def train_rf2(X_train: pd.DataFrame, y_train: pd.Series) -> RandomForestClassifier:
    """Cell 81: rf2 = RandomForestClassifier(n_estimators=15, max_depth=8,
    max_features=20, random_state=0); rf2.fit(X_train, y_train)."""
    rf2 = RandomForestClassifier(**RF2_PARAMS)
    rf2.fit(X_train, y_train)

    cv_rf2 = cross_val_score(rf2, X_train, y_train, cv=5)
    logger.info(
        "Random Forest Model 2 (rf2): mean cross-validation score=%.2f (scores=%s)",
        cv_rf2.mean(),
        ", ".join(map(str, cv_rf2)),
    )
    return rf2


# ==========================================================================
# Persist the trained bundle (backend.ml.artifacts format)
# ==========================================================================

def save_notebook_model_bundle(
    rf2: RandomForestClassifier,
    scaler: StandardScaler,
    ipca: IncrementalPCA,
    feature_names: list[str],
    result: evaluation.EvaluationResult,
    version_dir: Path,
) -> Path:
    metadata = artifacts.build_metadata(
        model_name=MODEL_NAME,
        dataset="CIC-IDS2017",
        accuracy=result.accuracy,
        precision=result.precision_macro,
        recall=result.recall_macro,
        f1_score=result.f1_macro,
        features=feature_names,
        pca_components=len(feature_names),
    )
    artifacts.save_model_bundle(
        version_dir=version_dir,
        model=rf2,
        scaler=scaler,
        pca=ipca,
        feature_names=feature_names,
        metadata=metadata,
    )
    logger.info(
        "Saved notebook model '%s' to %s (accuracy=%.4f)",
        MODEL_NAME,
        version_dir,
        result.accuracy,
    )
    return version_dir


# ==========================================================================
# End-to-end run
# ==========================================================================

def run(data_dir: str, models_dir: str = "models", force_version: Optional[int] = None) -> Path:
    """Train the notebook's rf2 on real CIC-IDS2017 data and save the bundle."""
    data = load_notebook_data(data_dir)
    data = clean_notebook_data(data)
    data = drop_invariant_columns(data)
    scaler, ipca, new_data = fit_scaler_and_pca(data)
    X_train, X_test, y_train, y_test = prepare_multiclass_dataset(new_data)
    rf2 = train_rf2(X_train, y_train)
    result = evaluation.evaluate_model(MODEL_NAME, rf2, X_test, y_test)

    if force_version is not None:
        version_dir = Path(models_dir) / f"v{force_version}"
        if version_dir.is_dir():
            shutil.rmtree(version_dir)
        version_dir.mkdir(parents=True, exist_ok=False)
    else:
        version_dir = artifacts.next_version_dir(models_dir)

    feature_names = [f"PC{i + 1}" for i in range(ipca.n_components_)]
    return save_notebook_model_bundle(rf2, scaler, ipca, feature_names, result, version_dir)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Train the final.ipynb rf2 model on real CIC-IDS2017 data and save it as a model version"
    )
    parser.add_argument("data_dir", help="Directory containing the raw CIC-IDS2017 CSV files")
    parser.add_argument("--models-dir", default="models", help="Root directory for versioned model output")
    parser.add_argument("--force-version", type=int, default=None, help="Write to a specific vN directory, replacing it")
    args = parser.parse_args()

    version_dir = run(args.data_dir, args.models_dir, args.force_version)
    print(f"\nNotebook model (rf2) trained and saved -> {version_dir}")
    print(f"Artifacts: {json.dumps([f.name for f in version_dir.iterdir()], indent=2)}")
    print("\nThe API loads the latest model version automatically (backend.ml.predictor.get_predictor()).")


if __name__ == "__main__":
    main()
