"""
Unit tests for backend/ml/inference.py - the full validation -> scaler ->
PCA -> model -> confidence -> severity pipeline.

Run with:
    python -m pytest tests/test_inference.py -v
"""

import math

import pytest

from backend.ml import inference
from backend.ml.predictor import Predictor
from backend.ml.schemas import PredictionResponse


def test_successful_prediction_returns_full_response(trained_model_dir, valid_feature_payload):
    predictor = Predictor(trained_model_dir)

    response = inference.predict(valid_feature_payload, predictor=predictor)

    assert isinstance(response, PredictionResponse)
    assert response.prediction in {"BENIGN", "DoS"}
    assert 0.0 <= response.confidence <= 100.0
    assert response.severity in {"Low", "Medium", "High", "Critical"}
    assert response.model_version == trained_model_dir.name
    assert response.latency_ms >= 0.0
    assert response.timestamp  # non-empty ISO timestamp


def test_prediction_label_matches_severity_mapping(trained_model_dir, valid_feature_payload):
    predictor = Predictor(trained_model_dir)
    response = inference.predict(valid_feature_payload, predictor=predictor)

    if response.prediction == "BENIGN":
        assert response.severity == "Low"
    elif response.prediction == "DoS":
        assert response.severity == "High"


def test_missing_feature_raises_feature_validation_failed(trained_model_dir, valid_feature_payload):
    predictor = Predictor(trained_model_dir)
    incomplete = dict(valid_feature_payload)
    del incomplete["Feature 0"]

    with pytest.raises(inference.FeatureValidationFailed) as exc_info:
        inference.predict(incomplete, predictor=predictor)

    error_types = {e.error_type for e in exc_info.value.errors}
    assert "missing_feature" in error_types


def test_wrong_datatype_raises_feature_validation_failed(trained_model_dir, valid_feature_payload):
    predictor = Predictor(trained_model_dir)
    bad_payload = dict(valid_feature_payload)
    bad_payload["Feature 0"] = "not-a-number"

    with pytest.raises(inference.FeatureValidationFailed) as exc_info:
        inference.predict(bad_payload, predictor=predictor)

    error_types = {e.error_type for e in exc_info.value.errors}
    assert "invalid_type" in error_types


def test_nan_value_raises_feature_validation_failed(trained_model_dir, valid_feature_payload):
    predictor = Predictor(trained_model_dir)
    bad_payload = dict(valid_feature_payload)
    bad_payload["Feature 0"] = math.nan

    with pytest.raises(inference.FeatureValidationFailed) as exc_info:
        inference.predict(bad_payload, predictor=predictor)

    error_types = {e.error_type for e in exc_info.value.errors}
    assert "nan_value" in error_types


def test_infinite_value_raises_feature_validation_failed(trained_model_dir, valid_feature_payload):
    predictor = Predictor(trained_model_dir)
    bad_payload = dict(valid_feature_payload)
    bad_payload["Feature 0"] = math.inf

    with pytest.raises(inference.FeatureValidationFailed) as exc_info:
        inference.predict(bad_payload, predictor=predictor)

    error_types = {e.error_type for e in exc_info.value.errors}
    assert "infinite_value" in error_types


def test_unexpected_column_raises_feature_validation_failed(trained_model_dir, valid_feature_payload):
    predictor = Predictor(trained_model_dir)
    bad_payload = dict(valid_feature_payload)
    bad_payload["Some Extra Column"] = 1.0

    with pytest.raises(inference.FeatureValidationFailed) as exc_info:
        inference.predict(bad_payload, predictor=predictor)

    error_types = {e.error_type for e in exc_info.value.errors}
    assert "unexpected_feature" in error_types


def test_custom_severity_map_is_respected(trained_model_dir, valid_feature_payload):
    predictor = Predictor(trained_model_dir)
    override_map = {"BENIGN": "Critical", "DoS": "Critical"}  # deliberately unrealistic, just to prove it's used

    response = inference.predict(valid_feature_payload, predictor=predictor, severity_map=override_map)
    assert response.severity == "Critical"


def test_feature_validation_failed_is_a_prediction_error(trained_model_dir):
    predictor = Predictor(trained_model_dir)
    with pytest.raises(inference.PredictionError):
        inference.predict({}, predictor=predictor)
