"""
Unit tests for backend/ml/confidence.py.

Run with:
    python -m pytest tests/test_confidence.py -v
"""

import numpy as np
import pytest
from sklearn.tree import DecisionTreeClassifier

from backend.ml.confidence import build_confidence_payload, compute_confidence


def _make_fitted_classifier() -> DecisionTreeClassifier:
    X = np.array([[0, 0], [0, 1], [1, 0], [1, 1]] * 10)
    y = np.array((["BENIGN"] * 2 + ["DoS"] * 2) * 10)
    clf = DecisionTreeClassifier(random_state=0)
    clf.fit(X, y)
    return clf


def test_compute_confidence_returns_label_and_percentage():
    clf = _make_fitted_classifier()
    label, confidence = compute_confidence(clf, np.array([[0, 0]]))

    assert label in {"BENIGN", "DoS"}
    assert 0.0 <= confidence <= 100.0


def test_compute_confidence_is_high_for_a_clean_decision_boundary():
    clf = _make_fitted_classifier()
    label, confidence = compute_confidence(clf, np.array([[0, 0]]))
    # This toy dataset has a perfectly clean split, so the tree should be fully confident.
    assert confidence == 100.0


def test_compute_confidence_rejects_multi_row_input():
    clf = _make_fitted_classifier()
    with pytest.raises(ValueError):
        compute_confidence(clf, np.array([[0, 0], [1, 1]]))


def test_build_confidence_payload_shape():
    payload = build_confidence_payload("DoS", 98.42)
    assert payload == {"prediction": "DoS", "confidence": 98.42}
