"""
Unit tests for backend/ml/preprocessing.py.

These tests use small, hand-built DataFrames rather than the real
CIC-IDS2017 CSVs, so they run in milliseconds and don't require the dataset
to be downloaded. `load_and_merge_dataset` (the one function that touches
disk) is tested separately using pytest's `tmp_path` fixture to create
throwaway CSV files.

Run with:
    python -m pytest tests/test_preprocessing.py -v
"""

import numpy as np
import pandas as pd
import pytest

from backend.ml.preprocessing import (
    DataLoadError,
    clean_column_names,
    drop_invariant_columns,
    handle_missing_and_infinite_values,
    load_and_merge_dataset,
    map_attack_labels,
    optimize_memory_usage,
    remove_duplicate_rows,
)


# --------------------------------------------------------------------------
# load_and_merge_dataset
# --------------------------------------------------------------------------

def test_load_and_merge_dataset_concatenates_all_files(tmp_path):
    df1 = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
    df2 = pd.DataFrame({"a": [5, 6], "b": [7, 8]})
    df1.to_csv(tmp_path / "day1.csv", index=False)
    df2.to_csv(tmp_path / "day2.csv", index=False)

    result = load_and_merge_dataset(str(tmp_path), filenames=["day1.csv", "day2.csv"])

    assert result.shape == (4, 2)
    assert list(result["a"]) == [1, 2, 5, 6]


def test_load_and_merge_dataset_raises_on_missing_directory():
    with pytest.raises(DataLoadError, match="directory not found"):
        load_and_merge_dataset("/path/does/not/exist", filenames=["x.csv"])


def test_load_and_merge_dataset_raises_on_missing_file(tmp_path):
    with pytest.raises(DataLoadError, match="not found"):
        load_and_merge_dataset(str(tmp_path), filenames=["missing.csv"])


# --------------------------------------------------------------------------
# clean_column_names
# --------------------------------------------------------------------------

def test_clean_column_names_strips_whitespace():
    df = pd.DataFrame({" Flow Duration": [1], "Label ": ["BENIGN"]})
    result = clean_column_names(df)
    assert list(result.columns) == ["Flow Duration", "Label"]


# --------------------------------------------------------------------------
# remove_duplicate_rows
# --------------------------------------------------------------------------

def test_remove_duplicate_rows_drops_exact_duplicates():
    df = pd.DataFrame({"a": [1, 1, 2], "b": [1, 1, 2]})
    result = remove_duplicate_rows(df)
    assert len(result) == 2
    assert list(result.index) == [0, 1]  # index reset


# --------------------------------------------------------------------------
# handle_missing_and_infinite_values
# --------------------------------------------------------------------------

def test_handle_missing_and_infinite_values_fills_with_median():
    df = pd.DataFrame({"x": [1.0, 2.0, np.inf, np.nan, 3.0]})
    result = handle_missing_and_infinite_values(df.copy())

    assert not np.isinf(result["x"]).any()
    assert not result["x"].isna().any()
    # Median of [1, 2, 3] (the finite, non-null values) is 2.0
    assert result["x"].iloc[2] == pytest.approx(2.0)
    assert result["x"].iloc[3] == pytest.approx(2.0)


def test_handle_missing_and_infinite_values_ignores_non_numeric_columns():
    df = pd.DataFrame({"x": [1.0, np.nan], "label": ["BENIGN", None]})
    result = handle_missing_and_infinite_values(df.copy())
    # Non-numeric column is left untouched (still has its None)
    assert result["label"].isna().sum() == 1


# --------------------------------------------------------------------------
# map_attack_labels
# --------------------------------------------------------------------------

def test_map_attack_labels_maps_known_labels():
    df = pd.DataFrame({"Label": ["BENIGN", "DoS Hulk", "PortScan"]})
    result = map_attack_labels(df)
    assert "Label" not in result.columns
    assert list(result["Attack Type"]) == ["BENIGN", "DoS", "Port Scan"]


def test_map_attack_labels_splits_web_attack_subtypes():
    df = pd.DataFrame({"Label": ["Web Attack \ufffd XSS", "Web Attack \ufffd Sql Injection"]})
    result = map_attack_labels(df)
    assert list(result["Attack Type"]) == ["XSS", "SQL Injection"]


def test_map_attack_labels_uses_keyword_fallback_for_unmapped_encoding():
    # Simulates a differently-encoded mojibake character than the one in
    # constants.ATTACK_MAP, to prove the fallback path works.
    df = pd.DataFrame({"Label": ["Web Attack ? XSS"]})
    result = map_attack_labels(df)
    assert result["Attack Type"].iloc[0] == "XSS"


def test_map_attack_labels_flags_truly_unknown_labels():
    df = pd.DataFrame({"Label": ["SomeBrandNewAttack2027"]})
    result = map_attack_labels(df)
    assert result["Attack Type"].iloc[0] == "UNKNOWN"


def test_map_attack_labels_raises_if_label_column_missing():
    df = pd.DataFrame({"NotLabel": ["BENIGN"]})
    with pytest.raises(KeyError):
        map_attack_labels(df)


# --------------------------------------------------------------------------
# drop_invariant_columns
# --------------------------------------------------------------------------

def test_drop_invariant_columns_removes_single_value_columns():
    df = pd.DataFrame({"constant": [1, 1, 1], "varying": [1, 2, 3]})
    result, dropped = drop_invariant_columns(df)
    assert dropped == ["constant"]
    assert list(result.columns) == ["varying"]


def test_drop_invariant_columns_no_op_when_nothing_invariant():
    df = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
    result, dropped = drop_invariant_columns(df)
    assert dropped == []
    assert result.shape == df.shape


# --------------------------------------------------------------------------
# optimize_memory_usage
# --------------------------------------------------------------------------

def test_optimize_memory_usage_downcasts_dtypes_without_changing_values():
    df = pd.DataFrame({
        "float_col": np.array([1.5, 2.5, 3.5], dtype="float64"),
        "int_col": np.array([1, 2, 3], dtype="int64"),
    })
    result = optimize_memory_usage(df.copy())

    assert result["float_col"].dtype != np.float64  # downcast to float32
    assert result["int_col"].dtype != np.int64       # downcast to a smaller int type
    np.testing.assert_array_almost_equal(result["float_col"], df["float_col"])
    np.testing.assert_array_equal(result["int_col"], df["int_col"])
