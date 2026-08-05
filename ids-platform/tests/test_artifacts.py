"""
Unit tests for backend/ml/artifacts.py.

Uses pytest's `tmp_path` fixture for every test so nothing touches a real
`models/` directory, and small dummy sklearn objects instead of a real
trained pipeline (this module doesn't care what it's persisting).

Run with:
    python -m pytest tests/test_artifacts.py -v
"""

import pytest
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier

from backend.ml import artifacts


# --------------------------------------------------------------------------
# Version directory management
# --------------------------------------------------------------------------

def test_list_versions_empty_when_no_models_dir(tmp_path):
    assert artifacts.list_versions(tmp_path / "models") == []


def test_next_version_dir_starts_at_v1(tmp_path):
    version_dir = artifacts.next_version_dir(tmp_path / "models")
    assert version_dir.name == "v1"
    assert version_dir.is_dir()


def test_next_version_dir_increments(tmp_path):
    models_dir = tmp_path / "models"
    v1 = artifacts.next_version_dir(models_dir)
    v2 = artifacts.next_version_dir(models_dir)
    assert v1.name == "v1"
    assert v2.name == "v2"


def test_latest_version_dir_returns_highest_version(tmp_path):
    models_dir = tmp_path / "models"
    artifacts.next_version_dir(models_dir)
    v2 = artifacts.next_version_dir(models_dir)

    assert artifacts.latest_version_dir(models_dir) == v2


def test_latest_version_dir_raises_when_none_exist(tmp_path):
    with pytest.raises(artifacts.ArtifactNotFoundError):
        artifacts.latest_version_dir(tmp_path / "models")


# --------------------------------------------------------------------------
# Model / scaler / pca save & load roundtrips
# --------------------------------------------------------------------------

def test_save_and_load_model_roundtrip(tmp_path):
    model = DecisionTreeClassifier(max_depth=3)
    artifacts.save_model(model, tmp_path)

    loaded = artifacts.load_model(tmp_path)
    assert isinstance(loaded, DecisionTreeClassifier)
    assert loaded.max_depth == 3


def test_load_model_raises_when_missing(tmp_path):
    with pytest.raises(artifacts.ArtifactNotFoundError):
        artifacts.load_model(tmp_path)


def test_save_and_load_scaler_roundtrip(tmp_path):
    scaler = StandardScaler()
    artifacts.save_scaler(scaler, tmp_path)

    loaded = artifacts.load_scaler(tmp_path)
    assert isinstance(loaded, StandardScaler)


# --------------------------------------------------------------------------
# feature_names.json / metadata.json
# --------------------------------------------------------------------------

def test_save_and_load_feature_names_roundtrip(tmp_path):
    names = ["PC1", "PC2", "PC3"]
    artifacts.save_feature_names(names, tmp_path)

    assert artifacts.load_feature_names(tmp_path) == names


def test_build_metadata_fills_required_schema_keys():
    metadata = artifacts.build_metadata(
        model_name="random_forest_2",
        dataset="CIC-IDS2017",
        accuracy=0.99,
        precision=0.98,
        recall=0.97,
        f1_score=0.975,
        features=["PC1", "PC2"],
        pca_components=2,
    )

    expected_keys = {
        "model_name", "dataset", "training_date", "accuracy", "precision",
        "recall", "f1_score", "features", "pca_components",
        "sklearn_version", "project_version",
    }
    assert expected_keys.issubset(metadata.keys())
    assert metadata["model_name"] == "random_forest_2"
    assert metadata["sklearn_version"]  # populated automatically
    assert metadata["project_version"]  # populated automatically


def test_save_and_load_metadata_roundtrip(tmp_path):
    metadata = artifacts.build_metadata(
        model_name="random_forest_2",
        dataset="CIC-IDS2017",
        accuracy=0.99,
        precision=0.98,
        recall=0.97,
        f1_score=0.975,
        features=["PC1", "PC2"],
        pca_components=2,
    )
    artifacts.save_metadata(metadata, tmp_path)

    loaded = artifacts.load_metadata(tmp_path)
    assert loaded["model_name"] == "random_forest_2"


# --------------------------------------------------------------------------
# Full bundle save/load
# --------------------------------------------------------------------------

def test_save_and_load_model_bundle_roundtrip(tmp_path):
    model = DecisionTreeClassifier(max_depth=3)
    scaler = StandardScaler()
    metadata = artifacts.build_metadata(
        model_name="decision_tree_1",
        dataset="CIC-IDS2017",
        accuracy=0.9,
        precision=0.9,
        recall=0.9,
        f1_score=0.9,
        features=["PC1"],
        pca_components=1,
    )

    # pca is optional-in-spirit here but required by save_model_bundle's
    # signature, so use a trivial fitted IncrementalPCA-like stand-in isn't
    # needed - artifacts.py only pickles whatever object it's given.
    from sklearn.decomposition import IncrementalPCA
    import numpy as np

    pca = IncrementalPCA(n_components=1)
    pca.partial_fit(np.random.default_rng(0).normal(size=(10, 3)))

    artifacts.save_model_bundle(
        version_dir=tmp_path,
        model=model,
        scaler=scaler,
        pca=pca,
        feature_names=["PC1"],
        metadata=metadata,
    )

    bundle = artifacts.load_model_bundle(tmp_path)
    assert isinstance(bundle["model"], DecisionTreeClassifier)
    assert isinstance(bundle["scaler"], StandardScaler)
    assert bundle["feature_names"] == ["PC1"]
    assert bundle["metadata"]["model_name"] == "decision_tree_1"
    assert "label_encoder" not in bundle  # not saved, so should be absent
