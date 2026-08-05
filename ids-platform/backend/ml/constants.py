"""
Static configuration for the ML pipeline: dataset filenames and label mappings.

These values are extracted directly from the original notebook (cells 9 and
45) so preprocessing.py stays free of hardcoded strings.
"""

from typing import Final

# --------------------------------------------------------------------------
# Raw CIC-IDS2017 CSV filenames, in the same order the notebook loaded them.
# Kept as a single source of truth so data_loader tests and the real pipeline
# always agree on what "the dataset" consists of.
# --------------------------------------------------------------------------
RAW_DATA_FILENAMES: Final[list[str]] = [
    "Monday-WorkingHours.pcap_ISCX.csv",
    "Tuesday-WorkingHours.pcap_ISCX.csv",
    "Wednesday-workingHours.pcap_ISCX.csv",
    "Thursday-WorkingHours-Morning-WebAttacks.pcap_ISCX.csv",
    "Thursday-WorkingHours-Afternoon-Infilteration.pcap_ISCX.csv",
    "Friday-WorkingHours-Morning.pcap_ISCX.csv",
    "Friday-WorkingHours-Afternoon-PortScan.pcap_ISCX.csv",
    "Friday-WorkingHours-Afternoon-DDos.pcap_ISCX.csv",
]

# --------------------------------------------------------------------------
# Raw `Label` -> grouped `Attack Type` mapping.
#
# NOTE - deliberate deviation from the original notebook (flagged and agreed
# in the Phase 1 planning step): the notebook grouped all three web attack
# labels into a single "Web Attack" bucket. Since the product roadmap
# (Phase 4) requires detecting SQL Injection and XSS as distinct attack
# categories, this mapping splits them out. This is a data-labeling change,
# not an algorithm change, so it does not affect which ML models are used.
#
# The web-attack label keys below contain a mojibake character ("\ufffd",
# the Unicode replacement character) exactly as found in the raw CIC-IDS2017
# CSVs. `map_attack_labels()` also applies a keyword-based fallback so this
# mapping is robust even if a differently-encoded CSV produces a different
# mangled character.
# --------------------------------------------------------------------------
ATTACK_MAP: Final[dict[str, str]] = {
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
    "Web Attack \ufffd Brute Force": "Web Attack - Brute Force",
    "Web Attack \ufffd XSS": "XSS",
    "Web Attack \ufffd Sql Injection": "SQL Injection",
    "Infiltration": "Infiltration",
    "Heartbleed": "Heartbleed",
}

# Keyword fallback used when a raw label isn't an exact match in ATTACK_MAP
# (e.g. due to a different mojibake character from a different encoding).
# Order matters: checked top to bottom, first match wins.
ATTACK_KEYWORD_FALLBACK: Final[list[tuple[str, str]]] = [
    ("sql injection", "SQL Injection"),
    ("xss", "XSS"),
    ("web attack", "Web Attack - Brute Force"),
]

# Label used when a raw `Label` value matches neither ATTACK_MAP nor any
# keyword fallback. Surfacing these as "UNKNOWN" rather than silently
# dropping or mis-mapping them makes data-quality issues visible.
UNKNOWN_ATTACK_LABEL: Final[str] = "UNKNOWN"

# ==========================================================================
# Milestone 2 additions below.
#
# Everything above this line is unchanged from Milestone 1. The constants
# below are extracted from the notebook's feature-engineering and model
# training cells (79-124) so feature_engineering.py, training.py and
# artifacts.py have a single, testable source of truth for hyperparameters,
# exactly like ATTACK_MAP above. No Milestone 1 value was modified.
# ==========================================================================

TARGET_COLUMN: Final[str] = "Attack Type"
BENIGN_LABEL: Final[str] = "BENIGN"

# --------------------------------------------------------------------------
# Feature engineering (StandardScaler + IncrementalPCA) - notebook cells 85-87.
# --------------------------------------------------------------------------
# The notebook derives n_components as `len(features.columns) // 2` at
# runtime rather than a fixed constant, so that logic stays in
# feature_engineering.py (it's a function of the input data, not a fixed
# config value). IPCA_BATCH_SIZE, however, was a literal in the notebook.
IPCA_BATCH_SIZE: Final[int] = 500

# --------------------------------------------------------------------------
# Shared training config - notebook cells 95, 112 (train_test_split calls)
# and 98-124 (every cross_val_score call).
# --------------------------------------------------------------------------
RANDOM_STATE: Final[int] = 0
TEST_SIZE: Final[float] = 0.25
CV_FOLDS: Final[int] = 5

# --------------------------------------------------------------------------
# Binary-classification dataset balancing - notebook cell 94.
# --------------------------------------------------------------------------
BINARY_SAMPLE_SIZE: Final[int] = 15000

# --------------------------------------------------------------------------
# Multi-class dataset balancing - notebook cell 110.
#
# NOTE - deliberate minimal safety fix (flagged, same spirit as the
# ATTACK_MAP deviation above): the notebook's `if len(df) > 2500:
# df.sample(n=5000, ...)` will raise if a class has between 2501 and 4999
# rows, because pandas can't sample more rows than exist without
# `replace=True`. training.py reproduces the notebook's intent (cap large
# classes at MULTICLASS_CAP_PER_CLASS) but samples
# `min(MULTICLASS_CAP_PER_CLASS, len(df))` so it can't crash on a class size
# the original notebook's fixed CIC-IDS2017 run happened not to hit. No
# other balancing logic (the >1950 floor, SMOTE afterwards) is changed.
# --------------------------------------------------------------------------
MULTICLASS_MIN_CLASS_COUNT: Final[int] = 1950
MULTICLASS_CAP_THRESHOLD: Final[int] = 2500
MULTICLASS_CAP_PER_CLASS: Final[int] = 5000

# --------------------------------------------------------------------------
# Binary classification hyperparameters - notebook cells 98, 100, 104, 105.
# Two models per algorithm, exactly as trained in the notebook.
# --------------------------------------------------------------------------
LOGISTIC_REGRESSION_PARAMS: Final[list[dict]] = [
    {"max_iter": 10000, "C": 0.1, "random_state": RANDOM_STATE, "solver": "saga"},
    {"max_iter": 15000, "C": 100, "random_state": RANDOM_STATE, "solver": "sag"},
]

SVM_PARAMS: Final[list[dict]] = [
    {"kernel": "poly", "C": 1, "random_state": RANDOM_STATE, "probability": True},
    {"kernel": "rbf", "C": 1, "gamma": 0.1, "random_state": RANDOM_STATE, "probability": True},
]

# --------------------------------------------------------------------------
# Multi-class classification hyperparameters - notebook cells 115, 116,
# 119, 120, 123, 124.
# --------------------------------------------------------------------------
RANDOM_FOREST_PARAMS: Final[list[dict]] = [
    {"n_estimators": 10, "max_depth": 6, "max_features": None, "random_state": RANDOM_STATE},
    {"n_estimators": 15, "max_depth": 8, "max_features": 20, "random_state": RANDOM_STATE},
]

DECISION_TREE_PARAMS: Final[list[dict]] = [
    {"max_depth": 6},
    {"max_depth": 8},
]

KNN_PARAMS: Final[list[dict]] = [
    {"n_neighbors": 16},
    {"n_neighbors": 8},
]

# --------------------------------------------------------------------------
# Best-performing model - notebook cell 170's written conclusion ("Random
# Forest is the best performing model followed by KNN and Decision Tree"),
# specifically Random Forest "Model 2" (index 1 in RANDOM_FOREST_PARAMS),
# per cell 165's explicit ranking ("Random Forest: Model 2"). artifacts.py
# uses this to know which trained multi-class model becomes rf_model.pkl.
# --------------------------------------------------------------------------
BEST_MODEL_ALGORITHM: Final[str] = "random_forest"
BEST_MODEL_VARIANT_INDEX: Final[int] = 1  # RANDOM_FOREST_PARAMS[1] == rf2

# Bumped whenever the ML layer's contract (feature set, model type, artifact
# schema) changes in a way downstream consumers should know about. Recorded
# in every metadata.json - see artifacts.py.
PROJECT_VERSION: Final[str] = "0.2.0"
