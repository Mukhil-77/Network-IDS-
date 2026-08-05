"""
Dataset loading and cleaning for the CIC-IDS2017 intrusion detection pipeline.

This module is a direct, function-based conversion of the notebook's data
loading and cleaning cells:

    Notebook cells  5-17  -> load_and_merge_dataset()
    Notebook cells 18-39  -> clean_column_names(), remove_duplicate_rows(),
                             handle_missing_and_infinite_values(),
                             optimize_memory_usage()
    Notebook cell   45    -> map_attack_labels()  (uses constants.ATTACK_MAP)
    Notebook cells 75-82  -> drop_invariant_columns()

No modeling, scaling, or PCA logic lives here - see feature_engineering.py
(Milestone 2+) for that. Keeping this module free of anything that needs to
be "fitted" and persisted means it has no state and no artifacts of its own;
it's pure data transformation, safe to re-run at any time.
"""

from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from backend.ml.constants import ATTACK_KEYWORD_FALLBACK, ATTACK_MAP, RAW_DATA_FILENAMES, UNKNOWN_ATTACK_LABEL
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class DataLoadError(Exception):
    """Raised when the raw CIC-IDS2017 CSV files cannot be loaded as expected."""


def load_and_merge_dataset(
    data_dir: str,
    filenames: Optional[list[str]] = None,
) -> pd.DataFrame:
    """
    Load the CIC-IDS2017 daily CSV files from `data_dir` and concatenate them
    into a single DataFrame.

    Converted from notebook cells 9-11. The notebook read each day's CSV
    into its own variable (data1..data8) and concatenated them; here the
    file list is data-driven (constants.RAW_DATA_FILENAMES) so adding or
    removing a day's file doesn't require touching this function.

    Args:
        data_dir: Directory containing the raw CIC-IDS2017 CSV files.
        filenames: Optional override of which filenames to load, in order.
            Defaults to constants.RAW_DATA_FILENAMES (all 8 standard days).

    Returns:
        A single concatenated DataFrame with a fresh RangeIndex.

    Raises:
        DataLoadError: If `data_dir` doesn't exist, a file is missing, or a
            file exists but fails to parse as CSV.
    """
    files_to_load = filenames if filenames is not None else RAW_DATA_FILENAMES
    data_path = Path(data_dir)

    if not data_path.is_dir():
        raise DataLoadError(f"Dataset directory not found: {data_dir}")

    frames: list[pd.DataFrame] = []
    for filename in files_to_load:
        file_path = data_path / filename
        if not file_path.is_file():
            raise DataLoadError(f"Expected dataset file not found: {file_path}")

        try:
            df = pd.read_csv(file_path)
        except (pd.errors.ParserError, pd.errors.EmptyDataError, UnicodeDecodeError) as exc:
            raise DataLoadError(f"Failed to parse '{file_path}': {exc}") from exc

        logger.info("Loaded '%s' -> %d rows, %d columns", filename, *df.shape)
        frames.append(df)

    if not frames:
        raise DataLoadError("No files were loaded; `filenames` resolved to an empty list.")

    merged = pd.concat(frames, ignore_index=True)
    logger.info(
        "Merged %d files -> %d rows, %d columns (%.1f MB in memory)",
        len(frames),
        merged.shape[0],
        merged.shape[1],
        merged.memory_usage(deep=True).sum() / (1024 ** 2),
    )
    return merged


def clean_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """
    Strip leading/trailing whitespace from column names.

    Converted from notebook cell 13. The raw CIC-IDS2017 CSVs are known to
    have inconsistent whitespace in headers (e.g. " Flow Duration" vs
    "Flow Duration"), which silently breaks column lookups downstream if
    left uncorrected.
    """
    renamed = {col: col.strip() for col in df.columns}
    n_changed = sum(1 for old, new in renamed.items() if old != new)
    if n_changed:
        logger.info("Stripped whitespace from %d column name(s)", n_changed)
    return df.rename(columns=renamed)


def remove_duplicate_rows(df: pd.DataFrame) -> pd.DataFrame:
    """
    Drop exact duplicate rows.

    Converted from notebook cells 20-21.
    """
    n_before = len(df)
    deduped = df.drop_duplicates()
    n_removed = n_before - len(deduped)
    logger.info("Removed %d duplicate row(s) (%d -> %d)", n_removed, n_before, len(deduped))
    return deduped.reset_index(drop=True)


def handle_missing_and_infinite_values(df: pd.DataFrame) -> pd.DataFrame:
    """
    Replace infinite values with NaN, then fill remaining NaNs in numeric
    columns with that column's median.

    Converted from notebook cells 24-27 and 35-37. The notebook identified
    `Flow Bytes/s` and `Flow Packets/s` as the columns affected by
    division-by-zero producing `inf`, but this function applies the same
    treatment generically to all numeric columns so it isn't silently wrong
    if a future dataset variant has infinities elsewhere.
    """
    numeric_cols = df.select_dtypes(include=[np.number]).columns

    n_infinite = np.isinf(df[numeric_cols]).sum().sum()
    if n_infinite:
        logger.info("Replacing %d infinite value(s) with NaN", int(n_infinite))
    df[numeric_cols] = df[numeric_cols].replace([np.inf, -np.inf], np.nan)

    n_missing_before = df[numeric_cols].isna().sum().sum()
    if n_missing_before:
        medians = df[numeric_cols].median()
        df[numeric_cols] = df[numeric_cols].fillna(medians)
        logger.info(
            "Filled %d missing numeric value(s) using per-column medians",
            int(n_missing_before),
        )

    return df


def optimize_memory_usage(df: pd.DataFrame) -> pd.DataFrame:
    """
    Downcast numeric columns to the smallest safe dtype to reduce memory
    footprint.

    Converted from notebook cell 38. Purely a memory optimization; does not
    change the values, only their storage precision (e.g. float64 -> float32).
    """
    mem_before = df.memory_usage(deep=True).sum() / (1024 ** 2)

    float_cols = df.select_dtypes(include=["float64"]).columns
    int_cols = df.select_dtypes(include=["int64"]).columns

    df[float_cols] = df[float_cols].apply(pd.to_numeric, downcast="float")
    df[int_cols] = df[int_cols].apply(pd.to_numeric, downcast="integer")

    mem_after = df.memory_usage(deep=True).sum() / (1024 ** 2)
    reduction_pct = (1 - mem_after / mem_before) * 100 if mem_before else 0.0
    logger.info(
        "Memory usage reduced from %.1f MB to %.1f MB (%.1f%% reduction)",
        mem_before,
        mem_after,
        reduction_pct,
    )
    return df


def map_attack_labels(
    df: pd.DataFrame,
    label_column: str = "Label",
    new_column: str = "Attack Type",
) -> pd.DataFrame:
    """
    Map the raw `Label` column to a grouped `Attack Type` column and drop
    the original `Label` column.

    Converted from notebook cells 45 and 47, using constants.ATTACK_MAP.
    Unlike the notebook, this function does not assume every raw label has
    an exact match in the map: any label not found in ATTACK_MAP is checked
    against ATTACK_KEYWORD_FALLBACK (to survive minor encoding differences
    in the mojibake web-attack labels), and anything still unmatched is set
    to constants.UNKNOWN_ATTACK_LABEL and logged as a warning rather than
    silently producing NaN.

    Args:
        df: DataFrame containing `label_column`.
        label_column: Name of the raw label column (default "Label").
        new_column: Name of the grouped attack-type column to create
            (default "Attack Type").

    Returns:
        DataFrame with `label_column` dropped and `new_column` added.

    Raises:
        KeyError: If `label_column` is not present in `df`.
    """
    if label_column not in df.columns:
        raise KeyError(f"Expected label column '{label_column}' not found in DataFrame")

    def _map_single_label(raw_label: str) -> str:
        if raw_label in ATTACK_MAP:
            return ATTACK_MAP[raw_label]

        lowered = raw_label.lower()
        for keyword, mapped_type in ATTACK_KEYWORD_FALLBACK:
            if keyword in lowered:
                return mapped_type

        return UNKNOWN_ATTACK_LABEL

    df[new_column] = df[label_column].astype(str).map(_map_single_label)

    n_unknown = int((df[new_column] == UNKNOWN_ATTACK_LABEL).sum())
    if n_unknown:
        unmatched_examples = (
            df.loc[df[new_column] == UNKNOWN_ATTACK_LABEL, label_column].unique()[:5]
        )
        logger.warning(
            "%d row(s) had a raw label with no known mapping (examples: %s)",
            n_unknown,
            list(unmatched_examples),
        )

    logger.info("Attack type distribution:\n%s", df[new_column].value_counts().to_string())

    return df.drop(columns=[label_column])


def drop_invariant_columns(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """
    Drop columns that contain only a single unique value across all rows.

    Converted from notebook cells 79-81. Invariant columns carry no signal
    for classification and only add noise/dimensionality.

    Returns:
        A tuple of (DataFrame with invariant columns removed, list of the
        column names that were dropped) - the dropped-columns list is
        returned (rather than only logged) because feature_engineering.py
        and metadata.json will need to record exactly which columns were
        excluded for reproducibility.
    """
    nunique = df.nunique()
    invariant_cols = nunique[nunique <= 1].index.tolist()

    if invariant_cols:
        logger.info("Dropping %d invariant column(s): %s", len(invariant_cols), invariant_cols)
    else:
        logger.info("No invariant columns found")

    return df.drop(columns=invariant_cols), invariant_cols


def preprocess_dataset(
    data_dir: str,
    filenames: Optional[list[str]] = None,
) -> pd.DataFrame:
    """
    Run the full loading + cleaning pipeline end to end, in the same order
    as the notebook.

    Steps:
        1. Load and merge the raw CSV files
        2. Clean column names
        3. Remove duplicate rows
        4. Handle missing/infinite values
        5. Map raw labels to grouped attack types
        6. Drop invariant columns
        7. Optimize memory usage

    This is the single entry point scripts/train_pipeline.py (Milestone 1's
    successor) will call - individual steps remain independently usable and
    independently testable (see tests/test_preprocessing.py).

    Args:
        data_dir: Directory containing the raw CIC-IDS2017 CSV files.
        filenames: Optional override of which files to load.

    Returns:
        A cleaned DataFrame with a grouped `Attack Type` column, ready for
        feature engineering (scaling + PCA).
    """
    logger.info("Starting preprocessing pipeline (data_dir=%s)", data_dir)

    df = load_and_merge_dataset(data_dir, filenames)
    df = clean_column_names(df)
    df = remove_duplicate_rows(df)
    df = handle_missing_and_infinite_values(df)
    df = map_attack_labels(df)
    df, _dropped_cols = drop_invariant_columns(df)
    df = optimize_memory_usage(df)

    logger.info("Preprocessing complete -> final shape %d rows, %d columns", *df.shape)
    return df


if __name__ == "__main__":
    # Manual smoke-test entry point:
    #   python -m backend.ml.preprocessing /path/to/raw/csv/dir
    import sys

    if len(sys.argv) != 2:
        print("Usage: python -m backend.ml.preprocessing <path_to_raw_csv_directory>")
        sys.exit(1)

    result_df = preprocess_dataset(sys.argv[1])
    print(result_df.head())
