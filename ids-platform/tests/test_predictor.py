"""
Unit tests for backend/ml/predictor.py.

Run with:
    python -m pytest tests/test_predictor.py -v
"""

import threading

import pandas as pd

from backend.ml import predictor as predictor_mod
from backend.ml.predictor import Predictor, get_predictor, is_loaded, reload_predictor


def _reset_singleton():
    """Predictor is a process-wide singleton; tests must not leak state between each other."""
    predictor_mod._predictor = None
    predictor_mod._loaded_version_dir = None


def test_predictor_loads_expected_artifacts(trained_model_dir):
    _reset_singleton()
    predictor = Predictor(trained_model_dir)

    assert predictor.model is not None
    assert predictor.scaler is not None
    assert predictor.pca is not None
    assert predictor.encoder is None  # fixture model trains directly on string labels, no encoder saved
    assert len(predictor.expected_features) == 8
    assert predictor.version_label == trained_model_dir.name


def test_predictor_decode_label_without_encoder_returns_model_output(trained_model_dir):
    predictor = Predictor(trained_model_dir)
    # No LabelEncoder was saved, so decode_label should pass the raw model output straight through.
    assert predictor.decode_label("DoS") == "DoS"


def test_predictor_transform_returns_pca_shaped_output(trained_model_dir):
    predictor = Predictor(trained_model_dir)
    row = pd.DataFrame([{name: 0.5 for name in predictor.expected_features}])

    transformed = predictor.transform(row)
    assert transformed.shape == (1, len(predictor.pca_feature_names))


def test_predictor_as_metadata_model_matches_saved_metadata(trained_model_dir):
    predictor = Predictor(trained_model_dir)
    metadata_model = predictor.as_metadata_model()

    assert metadata_model.model_version_dir == trained_model_dir.name
    assert metadata_model.dataset == "synthetic-test-fixture"


def test_get_predictor_is_a_singleton(trained_model_dir):
    _reset_singleton()
    p1 = get_predictor(version_dir=trained_model_dir)
    p2 = get_predictor(version_dir=trained_model_dir)
    assert p1 is p2
    assert is_loaded()
    _reset_singleton()


def test_reload_predictor_produces_a_fresh_instance(trained_model_dir):
    _reset_singleton()
    p1 = get_predictor(version_dir=trained_model_dir)
    p2 = reload_predictor(version_dir=trained_model_dir)
    assert p1 is not p2
    _reset_singleton()


def test_get_predictor_is_thread_safe(trained_model_dir):
    """Multiple threads racing to initialize the singleton should all get the same instance."""
    _reset_singleton()
    results = []
    barrier = threading.Barrier(8)

    def _load():
        barrier.wait()
        results.append(get_predictor(version_dir=trained_model_dir))

    threads = [threading.Thread(target=_load) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(results) == 8
    assert all(r is results[0] for r in results)
    _reset_singleton()
