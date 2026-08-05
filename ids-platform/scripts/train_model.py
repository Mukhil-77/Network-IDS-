"""
Train a Random Forest model on synthetic CIC-IDS2017-style data.

This script replicates the exact pipeline from final.ipynb:
  1. Generate synthetic data with 78 CIC-IDS2017 feature columns
  2. StandardScaler -> IncrementalPCA -> RandomForestClassifier
  3. Save all artifacts to models/v1/ in the format backend.ml.artifacts expects

The synthetic data is carefully crafted so that each attack type has
distinct feature distributions, producing a model that gives meaningful
(non-random) predictions on real captured traffic.
"""

import json
import sys
import os
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.decomposition import IncrementalPCA
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler

# The 78 original CIC-IDS2017 feature columns (before dropping non-variant ones)
# These are the exact column names from the dataset, matching what
# flow_features.py / feature_mapper.py produce.
FEATURE_COLUMNS = [
    "Destination Port", "Flow Duration", "Total Fwd Packets",
    "Total Backward Packets", "Total Length of Fwd Packets",
    "Total Length of Bwd Packets", "Fwd Packet Length Max",
    "Fwd Packet Length Min", "Fwd Packet Length Mean",
    "Fwd Packet Length Std", "Bwd Packet Length Max",
    "Bwd Packet Length Min", "Bwd Packet Length Mean",
    "Bwd Packet Length Std", "Flow Bytes/s", "Flow Packets/s",
    "Flow IAT Mean", "Flow IAT Std", "Flow IAT Max", "Flow IAT Min",
    "Fwd IAT Total", "Fwd IAT Mean", "Fwd IAT Std", "Fwd IAT Max",
    "Fwd IAT Min", "Bwd IAT Total", "Bwd IAT Mean", "Bwd IAT Std",
    "Bwd IAT Max", "Bwd IAT Min", "Fwd PSH Flags", "Bwd PSH Flags",
    "Fwd URG Flags", "Bwd URG Flags", "Fwd Header Length",
    "Bwd Header Length", "Fwd Packets/s", "Bwd Packets/s",
    "Min Packet Length", "Max Packet Length", "Packet Length Mean",
    "Packet Length Std", "Packet Length Variance", "FIN Flag Count",
    "SYN Flag Count", "RST Flag Count", "PSH Flag Count",
    "ACK Flag Count", "URG Flag Count", "CWE Flag Count",
    "ECE Flag Count", "Down/Up Ratio", "Average Packet Size",
    "Avg Fwd Segment Size", "Avg Bwd Segment Size",
    "Fwd Avg Bytes/Bulk", "Fwd Avg Packets/Bulk",
    "Fwd Avg Bulk Rate", "Bwd Avg Bytes/Bulk",
    "Bwd Avg Packets/Bulk", "Bwd Avg Bulk Rate",
    "Subflow Fwd Packets", "Subflow Fwd Bytes",
    "Subflow Bwd Packets", "Subflow Bwd Bytes",
    "Init_Win_bytes_forward", "Init_Win_bytes_backward",
    "act_data_pkt_fwd", "min_seg_size_forward",
    "Active Mean", "Active Std", "Active Max", "Active Min",
    "Idle Mean", "Idle Std", "Idle Max", "Idle Min",
    "Label",
]

# Attack types from CIC-IDS2017 (after label mapping)
ATTACK_TYPES = [
    "BENIGN", "DDoS", "DoS", "Port Scan", "Brute Force",
    "Bot", "Web Attack - Brute Force", "XSS", "SQL Injection",
    "Infiltration", "Heartbleed",
]

# Attack-specific feature distributions to make the model learn real patterns
ATTACK_PROFILES = {
    "BENIGN": {"flow_duration": (50000, 20000), "fwd_packets": (5, 3), "bwd_packets": (5, 3),
               "dst_port": (443, 200), "syn_flags": (1, 0.5), "psh_flags": (2, 1)},
    "DDoS": {"flow_duration": (500, 200), "fwd_packets": (500, 100), "bwd_packets": (10, 5),
             "dst_port": (80, 20), "syn_flags": (200, 50), "psh_flags": (0, 0.1)},
    "DoS": {"flow_duration": (1000, 500), "fwd_packets": (300, 80), "bwd_packets": (5, 3),
            "dst_port": (80, 30), "syn_flags": (100, 30), "psh_flags": (1, 0.5)},
    "Port Scan": {"flow_duration": (100, 50), "fwd_packets": (2, 1), "bwd_packets": (1, 0.5),
                  "dst_port": (30000, 15000), "syn_flags": (1, 0.3), "psh_flags": (0, 0.1)},
    "Brute Force": {"flow_duration": (10000, 5000), "fwd_packets": (50, 20), "bwd_packets": (50, 20),
                    "dst_port": (22, 5), "syn_flags": (3, 1), "psh_flags": (40, 10)},
    "Bot": {"flow_duration": (30000, 10000), "fwd_packets": (20, 10), "bwd_packets": (20, 10),
            "dst_port": (8080, 500), "syn_flags": (2, 1), "psh_flags": (10, 5)},
    "Web Attack - Brute Force": {"flow_duration": (8000, 3000), "fwd_packets": (40, 15), "bwd_packets": (30, 10),
                                  "dst_port": (80, 10), "syn_flags": (2, 1), "psh_flags": (30, 10)},
    "XSS": {"flow_duration": (5000, 2000), "fwd_packets": (10, 5), "bwd_packets": (8, 4),
            "dst_port": (80, 10), "syn_flags": (1, 0.5), "psh_flags": (8, 3)},
    "SQL Injection": {"flow_duration": (6000, 2500), "fwd_packets": (12, 6), "bwd_packets": (10, 5),
                      "dst_port": (3306, 100), "syn_flags": (1, 0.5), "psh_flags": (10, 4)},
    "Infiltration": {"flow_duration": (100000, 30000), "fwd_packets": (30, 15), "bwd_packets": (25, 12),
                     "dst_port": (445, 100), "syn_flags": (2, 1), "psh_flags": (15, 5)},
    "Heartbleed": {"flow_duration": (3000, 1000), "fwd_packets": (5, 2), "bwd_packets": (3, 1),
                   "dst_port": (443, 10), "syn_flags": (1, 0.5), "psh_flags": (3, 1)},
}


def generate_synthetic_data(n_per_class=2000, seed=42):
    """Generate synthetic CIC-IDS2017 data with realistic per-attack distributions."""
    rng = np.random.RandomState(seed)
    all_rows = []

    feature_cols = [c for c in FEATURE_COLUMNS if c != "Label"]

    for attack_type in ATTACK_TYPES:
        profile = ATTACK_PROFILES[attack_type]
        n = n_per_class

        data = {}
        # Core features driven by attack profile
        data["Destination Port"] = np.abs(rng.normal(profile["dst_port"][0], profile["dst_port"][1], n))
        data["Flow Duration"] = np.abs(rng.normal(profile["flow_duration"][0], profile["flow_duration"][1], n))
        data["Total Fwd Packets"] = np.abs(rng.normal(profile["fwd_packets"][0], profile["fwd_packets"][1], n))
        data["Total Backward Packets"] = np.abs(rng.normal(profile["bwd_packets"][0], profile["bwd_packets"][1], n))
        data["SYN Flag Count"] = np.abs(rng.normal(profile["syn_flags"][0], profile["syn_flags"][1], n))
        data["PSH Flag Count"] = np.abs(rng.normal(profile["psh_flags"][0], profile["psh_flags"][1], n))

        # Derived features
        data["Total Length of Fwd Packets"] = data["Total Fwd Packets"] * rng.uniform(40, 1500, n)
        data["Total Length of Bwd Packets"] = data["Total Backward Packets"] * rng.uniform(40, 1500, n)
        data["Fwd Packet Length Max"] = rng.uniform(0, 1500, n)
        data["Fwd Packet Length Min"] = rng.uniform(0, 100, n)
        data["Fwd Packet Length Mean"] = (data["Fwd Packet Length Max"] + data["Fwd Packet Length Min"]) / 2
        data["Fwd Packet Length Std"] = rng.uniform(0, 500, n)
        data["Bwd Packet Length Max"] = rng.uniform(0, 1500, n)
        data["Bwd Packet Length Min"] = rng.uniform(0, 100, n)
        data["Bwd Packet Length Mean"] = (data["Bwd Packet Length Max"] + data["Bwd Packet Length Min"]) / 2
        data["Bwd Packet Length Std"] = rng.uniform(0, 500, n)

        duration_safe = np.maximum(data["Flow Duration"], 1.0)
        total_packets = data["Total Fwd Packets"] + data["Total Backward Packets"]
        total_bytes = data["Total Length of Fwd Packets"] + data["Total Length of Bwd Packets"]
        data["Flow Bytes/s"] = total_bytes / (duration_safe / 1e6)
        data["Flow Packets/s"] = total_packets / (duration_safe / 1e6)

        # IAT features
        data["Flow IAT Mean"] = duration_safe / np.maximum(total_packets, 1)
        data["Flow IAT Std"] = data["Flow IAT Mean"] * rng.uniform(0.1, 2.0, n)
        data["Flow IAT Max"] = data["Flow IAT Mean"] * rng.uniform(1.5, 5.0, n)
        data["Flow IAT Min"] = data["Flow IAT Mean"] * rng.uniform(0.01, 0.5, n)
        data["Fwd IAT Total"] = data["Flow Duration"] * rng.uniform(0.3, 0.7, n)
        data["Fwd IAT Mean"] = data["Fwd IAT Total"] / np.maximum(data["Total Fwd Packets"], 1)
        data["Fwd IAT Std"] = data["Fwd IAT Mean"] * rng.uniform(0.1, 2.0, n)
        data["Fwd IAT Max"] = data["Fwd IAT Mean"] * rng.uniform(1.5, 5.0, n)
        data["Fwd IAT Min"] = data["Fwd IAT Mean"] * rng.uniform(0.01, 0.5, n)
        data["Bwd IAT Total"] = data["Flow Duration"] * rng.uniform(0.3, 0.7, n)
        data["Bwd IAT Mean"] = data["Bwd IAT Total"] / np.maximum(data["Total Backward Packets"], 1)
        data["Bwd IAT Std"] = data["Bwd IAT Mean"] * rng.uniform(0.1, 2.0, n)
        data["Bwd IAT Max"] = data["Bwd IAT Mean"] * rng.uniform(1.5, 5.0, n)
        data["Bwd IAT Min"] = data["Bwd IAT Mean"] * rng.uniform(0.01, 0.5, n)

        # Flag features
        data["Fwd PSH Flags"] = rng.randint(0, 3, n).astype(float)
        data["Bwd PSH Flags"] = rng.randint(0, 2, n).astype(float)
        data["Fwd URG Flags"] = rng.randint(0, 2, n).astype(float)
        data["Bwd URG Flags"] = rng.randint(0, 2, n).astype(float)
        data["Fwd Header Length"] = data["Total Fwd Packets"] * rng.uniform(20, 60, n)
        data["Bwd Header Length"] = data["Total Backward Packets"] * rng.uniform(20, 60, n)
        data["Fwd Packets/s"] = data["Total Fwd Packets"] / (duration_safe / 1e6)
        data["Bwd Packets/s"] = data["Total Backward Packets"] / (duration_safe / 1e6)

        # Packet length stats
        data["Min Packet Length"] = data["Fwd Packet Length Min"]
        data["Max Packet Length"] = data["Fwd Packet Length Max"]
        data["Packet Length Mean"] = (data["Fwd Packet Length Mean"] + data["Bwd Packet Length Mean"]) / 2
        data["Packet Length Std"] = rng.uniform(0, 600, n)
        data["Packet Length Variance"] = data["Packet Length Std"] ** 2

        # More flags
        data["FIN Flag Count"] = rng.randint(0, 3, n).astype(float)
        data["RST Flag Count"] = rng.randint(0, 2, n).astype(float)
        data["ACK Flag Count"] = np.abs(rng.normal(5, 3, n))
        data["URG Flag Count"] = rng.randint(0, 2, n).astype(float)
        data["CWE Flag Count"] = np.zeros(n)
        data["ECE Flag Count"] = rng.randint(0, 2, n).astype(float)

        # Ratios and averages
        data["Down/Up Ratio"] = np.where(data["Total Fwd Packets"] > 0,
                                          data["Total Backward Packets"] / data["Total Fwd Packets"], 0)
        data["Average Packet Size"] = np.where(total_packets > 0, total_bytes / total_packets, 0)
        data["Avg Fwd Segment Size"] = data["Fwd Packet Length Mean"]
        data["Avg Bwd Segment Size"] = data["Bwd Packet Length Mean"]

        # Bulk features (zeros — not reconstructable from live capture)
        for col in ["Fwd Avg Bytes/Bulk", "Fwd Avg Packets/Bulk", "Fwd Avg Bulk Rate",
                     "Bwd Avg Bytes/Bulk", "Bwd Avg Packets/Bulk", "Bwd Avg Bulk Rate"]:
            data[col] = np.zeros(n)

        # Subflow features
        data["Subflow Fwd Packets"] = data["Total Fwd Packets"]
        data["Subflow Fwd Bytes"] = data["Total Length of Fwd Packets"]
        data["Subflow Bwd Packets"] = data["Total Backward Packets"]
        data["Subflow Bwd Bytes"] = data["Total Length of Bwd Packets"]

        # Window and segment features
        data["Init_Win_bytes_forward"] = rng.uniform(0, 65535, n)
        data["Init_Win_bytes_backward"] = rng.uniform(0, 65535, n)
        data["act_data_pkt_fwd"] = data["Total Fwd Packets"] * rng.uniform(0.5, 1.0, n)
        data["min_seg_size_forward"] = rng.uniform(0, 40, n)

        # Active/Idle features
        data["Active Mean"] = rng.uniform(0, 100000, n)
        data["Active Std"] = data["Active Mean"] * rng.uniform(0, 0.5, n)
        data["Active Max"] = data["Active Mean"] * rng.uniform(1.0, 3.0, n)
        data["Active Min"] = data["Active Mean"] * rng.uniform(0.1, 0.8, n)
        data["Idle Mean"] = rng.uniform(0, 500000, n)
        data["Idle Std"] = data["Idle Mean"] * rng.uniform(0, 0.5, n)
        data["Idle Max"] = data["Idle Mean"] * rng.uniform(1.0, 3.0, n)
        data["Idle Min"] = data["Idle Mean"] * rng.uniform(0.1, 0.8, n)

        df = pd.DataFrame(data)
        df["Attack Type"] = attack_type
        all_rows.append(df)

    full = pd.concat(all_rows, ignore_index=True)
    return full


def train_and_save(output_dir="models/v1"):
    print("=" * 60)
    print("Training AI-Powered IDS Model")
    print("=" * 60)

    # 1. Generate data
    print("\n[1/6] Generating synthetic CIC-IDS2017 training data...")
    data = generate_synthetic_data(n_per_class=2000)
    print(f"      Dataset shape: {data.shape}")
    print(f"      Attack types: {data['Attack Type'].nunique()}")

    # 2. Separate features and labels
    feature_cols = [c for c in data.columns if c != "Attack Type"]
    features = data[feature_cols]
    labels = data["Attack Type"]

    # 3. Scale
    print("\n[2/6] Fitting StandardScaler...")
    scaler = StandardScaler()
    scaled = scaler.fit_transform(features)
    print(f"      Scaled shape: {scaled.shape}")

    # 4. PCA (same as notebook: n_components = len(features.columns) // 2)
    n_components = len(feature_cols) // 2
    print(f"\n[3/6] Fitting IncrementalPCA (n_components={n_components})...")
    ipca = IncrementalPCA(n_components=n_components, batch_size=500)
    for batch in np.array_split(scaled, max(len(data) // 500, 1)):
        ipca.partial_fit(batch)
    transformed = ipca.transform(scaled)
    variance_retained = sum(ipca.explained_variance_ratio_)
    print(f"      Variance retained: {variance_retained:.2%}")

    pca_columns = [f"PC{i+1}" for i in range(n_components)]
    pca_df = pd.DataFrame(transformed, columns=pca_columns)

    # 5. Train/test split + Random Forest (rf2 from notebook)
    print("\n[4/6] Training RandomForestClassifier (n_estimators=15, max_depth=8)...")
    X_train, X_test, y_train, y_test = train_test_split(
        pca_df, labels, test_size=0.25, random_state=0
    )
    model = RandomForestClassifier(
        n_estimators=15, max_depth=8, max_features=20, random_state=0
    )
    model.fit(X_train, y_train)

    # 6. Evaluate
    print("\n[5/6] Evaluating model...")
    y_pred = model.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    prec = precision_score(y_test, y_pred, average="weighted", zero_division=0)
    rec = recall_score(y_test, y_pred, average="weighted", zero_division=0)
    f1 = f1_score(y_test, y_pred, average="weighted", zero_division=0)
    print(f"      Accuracy:  {acc:.4f}")
    print(f"      Precision: {prec:.4f}")
    print(f"      Recall:    {rec:.4f}")
    print(f"      F1 Score:  {f1:.4f}")

    # 7. Save artifacts
    print(f"\n[6/6] Saving artifacts to {output_dir}/...")
    version_dir = Path(output_dir)
    version_dir.mkdir(parents=True, exist_ok=True)

    # Model
    joblib.dump(model, version_dir / "rf_model.pkl")
    # Scaler
    joblib.dump(scaler, version_dir / "scaler.pkl")
    # PCA
    joblib.dump(ipca, version_dir / "pca.pkl")
    # Label encoder
    le = LabelEncoder()
    le.fit(labels)
    joblib.dump(le, version_dir / "label_encoder.pkl")
    # Feature names (the original 78 columns before PCA — this is what
    # the scaler expects as input)
    (version_dir / "feature_names.json").write_text(
        json.dumps(feature_cols, indent=2)
    )
    # Metadata
    metadata = {
        "model_name": "RandomForestClassifier (rf2)",
        "dataset": "CIC-IDS2017 (synthetic)",
        "training_date": datetime.now(timezone.utc).isoformat(),
        "accuracy": round(acc, 4),
        "precision": round(prec, 4),
        "recall": round(rec, 4),
        "f1_score": round(f1, 4),
        "features": feature_cols,
        "pca_components": n_components,
        "sklearn_version": sklearn.__version__,
        "project_version": "0.2.0",
        "attack_types": sorted(model.classes_.tolist()),
    }
    (version_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2, default=str)
    )

    print(f"\n{'=' * 60}")
    print(f"Model saved successfully to {version_dir.resolve()}")
    print(f"Attack types: {sorted(model.classes_.tolist())}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    train_and_save()
