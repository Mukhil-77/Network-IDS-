"""
Unit tests for backend/ml/validator.py.

Run with:
    python -m pytest tests/test_validator.py -v
"""

import math

import pytest

from backend.ml.validator import (
    FeatureValidationError,
    build_ordered_frame,
    validate_and_raise,
    validate_features,
)

EXPECTED = ["a", "b", "c"]


def test_valid_input_produces_no_errors():
    errors = validate_features({"a": 1.0, "b": 2.0, "c": 3.0}, EXPECTED)
    assert errors == []


def test_missing_feature_is_reported():
    errors = validate_features({"a": 1.0, "b": 2.0}, EXPECTED)
    error_types = {(e.field, e.error_type) for e in errors}
    assert ("c", "missing_feature") in error_types


def test_unexpected_feature_is_reported():
    errors = validate_features({"a": 1.0, "b": 2.0, "c": 3.0, "d": 4.0}, EXPECTED)
    error_types = {(e.field, e.error_type) for e in errors}
    assert ("d", "unexpected_feature") in error_types


def test_invalid_datatype_is_reported():
    errors = validate_features({"a": "not-a-number", "b": 2.0, "c": 3.0}, EXPECTED)
    error_types = {(e.field, e.error_type) for e in errors}
    assert ("a", "invalid_type") in error_types


def test_numeric_string_is_accepted():
    errors = validate_features({"a": "1.5", "b": 2.0, "c": 3.0}, EXPECTED)
    assert errors == []


def test_boolean_is_rejected_as_invalid_type():
    # bool is technically a Real subclass in Python; explicitly rejected
    # since "true"/"false" is never a legitimate CIC-IDS2017 feature value.
    errors = validate_features({"a": True, "b": 2.0, "c": 3.0}, EXPECTED)
    error_types = {(e.field, e.error_type) for e in errors}
    assert ("a", "invalid_type") in error_types


def test_nan_value_is_reported():
    errors = validate_features({"a": math.nan, "b": 2.0, "c": 3.0}, EXPECTED)
    error_types = {(e.field, e.error_type) for e in errors}
    assert ("a", "nan_value") in error_types


def test_infinite_value_is_reported():
    errors = validate_features({"a": math.inf, "b": 2.0, "c": 3.0}, EXPECTED)
    error_types = {(e.field, e.error_type) for e in errors}
    assert ("a", "infinite_value") in error_types


def test_negative_infinite_value_is_reported():
    errors = validate_features({"a": -math.inf, "b": 2.0, "c": 3.0}, EXPECTED)
    error_types = {(e.field, e.error_type) for e in errors}
    assert ("a", "infinite_value") in error_types


def test_multiple_errors_all_accumulate():
    errors = validate_features({"a": math.nan, "d": 1.0}, EXPECTED)
    error_types = {(e.field, e.error_type) for e in errors}
    assert ("a", "nan_value") in error_types
    assert ("d", "unexpected_feature") in error_types
    assert ("b", "missing_feature") in error_types
    assert ("c", "missing_feature") in error_types
    assert len(errors) == 4


def test_validate_and_raise_raises_on_errors():
    with pytest.raises(FeatureValidationError) as exc_info:
        validate_and_raise({"a": 1.0}, EXPECTED)
    assert len(exc_info.value.errors) > 0


def test_validate_and_raise_does_not_raise_on_valid_input():
    validate_and_raise({"a": 1.0, "b": 2.0, "c": 3.0}, EXPECTED)  # should not raise


def test_build_ordered_frame_orders_columns_correctly():
    df = build_ordered_frame({"c": 3.0, "a": 1.0, "b": 2.0}, EXPECTED)
    assert list(df.columns) == EXPECTED
    assert df.iloc[0].tolist() == [1.0, 2.0, 3.0]
