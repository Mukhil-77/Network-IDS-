"""
Dataset abstraction layer for multi-dataset IDS evaluation.

This module provides a unified interface for loading, preprocessing, and
harmonizing features across multiple IDS datasets:
- CIC-IDS2017 (primary)
- UNSW-NB15
- CIC-IDS2018
- TON-IoT
- CICIoT2023

Provides feature harmonization layer to map different datasets to a common
feature space for cross-dataset evaluation.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, List, Tuple, Any
from enum import Enum

import numpy as np
import pandas as pd

from backend.ml.preprocessing import preprocess_dataset as preprocess_cicids2017
from backend.ml.constants import TARGET_COLUMN, ATTACK_MAP, UNKNOWN_ATTACK_LABEL
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class DatasetType(Enum):
    """Supported dataset types for cross-dataset evaluation."""
    CIC_IDS_2017 = "cic_ids_2017"
    UNSW_NB15 = "unsw_nb15"
    CIC_IDS_2018 = "cic_ids_2018"
    TON_IOT = "ton_iot"
    CIC_IOT_2023 = "cic_iot_2023"


@dataclass
class DatasetInfo:
    """Metadata about a dataset."""
    name: str
    dataset_type: DatasetType
    path: Path
    attack_types: List[str]
    num_samples: int
    num_features: int
    class_distribution: Dict[str, int]
    feature_names: List[str]


@dataclass
class FeatureMapping:
    """Mapping from dataset-specific features to common feature space."""
    dataset_type: DatasetType
    common_features: List[str]           # Features in common space
    dataset_features: List[str]          # Original feature names
    feature_mapping: Dict[str, str]      # common_name -> dataset_name
    missing_features: List[str]          # Common features not in dataset
    extra_features: List[str]            # Dataset features not in common space


class BaseDatasetLoader(ABC):
    """Abstract base class for dataset loaders."""
    
    @abstractmethod
    def load_raw(self, data_dir: str) -> pd.DataFrame:
        """Load raw dataset from directory."""
        pass
    
    @abstractmethod
    def preprocess(self, df: pd.DataFrame) -> pd.DataFrame:
        """Preprocess raw dataframe to standard format."""
        pass
    
    @abstractmethod
    def get_attack_types(self) -> List[str]:
        """Return list of attack types in this dataset."""
        pass
    
    @abstractmethod
    def get_feature_names(self) -> List[str]:
        """Return feature names (excluding target)."""
        pass


class CICIDS2017Loader(BaseDatasetLoader):
    """Loader for CIC-IDS2017 dataset (existing implementation)."""
    
    def load_raw(self, data_dir: str) -> pd.DataFrame:
        from backend.ml.preprocessing import load_and_merge_dataset
        return load_and_merge_dataset(data_dir)
    
    def preprocess(self, df: pd.DataFrame) -> pd.DataFrame:
        from backend.ml.preprocessing import preprocess_dataset
        return preprocess_dataset(df)
    
    def get_attack_types(self) -> List[str]:
        return [
            "BENIGN", "DDoS", "DoS", "Port Scan", "Bot", 
            "Web Attack - Brute Force", "XSS", "SQL Injection",
            "Infiltration", "Heartbleed", "UNKNOWN"
        ]
    
    def get_feature_names(self) -> List[str]:
        return []


class DatasetRegistry:
    """Registry for dataset loaders and feature harmonization."""
    
    def __init__(self):
        self._loaders: Dict[DatasetType, BaseDatasetLoader] = {
            DatasetType.CIC_IDS_2017: CICIDS2017Loader(),
        }
        self._common_features: Optional[List[str]] = None
        self._feature_mappings: Dict[DatasetType, FeatureMapping] = {}
    
    def register_loader(self, dataset_type: DatasetType, loader: BaseDatasetLoader):
        """Register a new dataset loader."""
        self._loaders[dataset_type] = loader
        logger.info(f"Registered loader for {dataset_type.value}")
    
    def get_loader(self, dataset_type: DatasetType) -> BaseDatasetLoader:
        """Get loader for dataset type."""
        if dataset_type not in self._loaders:
            raise ValueError(f"No loader registered for {dataset_type.value}")
        return self._loaders[dataset_type]
    
    def load_dataset(self, dataset_type: DatasetType, data_dir: str) -> pd.DataFrame:
        """Load and preprocess dataset."""
        loader = self.get_loader(dataset_type)
        raw_df = loader.load_raw(data_dir)
        processed_df = loader.preprocess(raw_df)
        logger.info(f"Loaded {dataset_type.value}: {len(raw_df)} rows, {len(loader.get_feature_names())} features")
        return raw_df
    
    def compute_common_features(self, datasets: Dict[DatasetType, pd.DataFrame]) -> List[str]:
        """
        Compute common feature set across multiple datasets.
        Returns intersection of feature names across all datasets.
        """
        feature_sets = {}
        for dtype, df in datasets.items():
            numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
            target_cols = [TARGET_COLUMN, 'Label', 'attack_cat', 'Attack_Type', 'attack_type']
            feature_cols = [c for c in numeric_cols if c not in target_cols]
            feature_sets[dtype] = set(feature_cols)
        
        if not feature_sets:
            return []
        
        common = set.intersection(*feature_sets.values())
        common_list = sorted(list(common))
        self._common_features = common_list
        logger.info(f"Computed {len(common_list)} common features across {len(datasets)} datasets")
        return common_list
    
    def get_common_features(self) -> Optional[List[str]]:
        return self._common_features
    
    def harmonize_features(
        self, 
        df: pd.DataFrame, 
        dataset_type: DatasetType,
        common_features: Optional[List[str]] = None
    ) -> Tuple[pd.DataFrame, FeatureMapping]:
        """
        Harmonize dataset features to common feature space.
        
        Returns harmonized dataframe and feature mapping info.
        """
        if common_features is None:
            common_features = self._common_features
            if common_features is None:
                raise ValueError("Common features not computed. Call compute_common_features first.")
        
        target_cols = [TARGET_COLUMN, 'Label', 'attack_cat', 'Attack_Type', 'attack_type']
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        dataset_features = [c for c in numeric_cols if c not in target_cols]
        
        feature_mapping = {}
        missing_features = []
        for cf in common_features:
            if cf in dataset_features:
                feature_mapping[cf] = cf
            else:
                missing_features.append(cf)
        
        extra_features = [f for f in dataset_features if f not in common_features]
        
        target_col = None
        for tc in [TARGET_COLUMN, 'Label', 'attack_cat', 'Attack_Type', 'attack_type']:
            if tc in df.columns:
                target_col = tc
                break
        
        harmonized_cols = [f for f in common_features if f in df.columns]
        if target_col:
            harmonized_cols.append(target_col)
        
        harmonized_df = df[harmonized_cols].copy()
        
        mapping = FeatureMapping(
            dataset_type=dataset_type,
            common_features=common_features,
            dataset_features=dataset_features,
            feature_mapping=feature_mapping,
            missing_features=missing_features,
            extra_features=extra_features,
        )
        
        self._feature_mappings[dataset_type] = mapping
        logger.info(f"Harmonized {dataset_type.value}: {len(harmonized_cols)} common features, "
                   f"{len(missing_features)} missing, {len(extra_features)} extra")
        
        return harmonized_df, mapping
    
    def get_feature_mapping(self, dataset_type: DatasetType) -> Optional[FeatureMapping]:
        return self._feature_mappings.get(dataset_type)


# Global registry instance
dataset_registry = DatasetRegistry()


def load_dataset_for_cross_evaluation(
    dataset_type: DatasetType, 
    data_dir: str
) -> pd.DataFrame:
    """Convenience function to load dataset for cross-evaluation."""
    return dataset_registry.load_dataset(dataset_type, data_dir)


def compute_cross_dataset_features(
    dataset_dirs: Dict[DatasetType, str]
) -> List[str]:
    """
    Load multiple datasets and compute common feature set.
    
    Args:
        dataset_dirs: Dict mapping dataset type to data directory path
        
    Returns:
        List of common feature names
    """
    datasets = {}
    for dtype, data_dir in dataset_dirs.items():
        loader = dataset_registry.get_loader(dtype)
        raw_df = loader.load_raw(data_dir)
        datasets[dtype] = raw_df
    
    return dataset_registry.compute_common_features(datasets)


def harmonize_all_datasets(
    dataset_dirs: Dict[DatasetType, str],
    common_features: Optional[List[str]] = None
) -> Dict[DatasetType, Tuple[pd.DataFrame, FeatureMapping]]:
    """
    Load and harmonize multiple datasets to common feature space.
    
    Args:
        dataset_dirs: Dict mapping dataset type to data directory
        common_features: Optional pre-computed common features
        
    Returns:
        Dict mapping dataset_type to (harmonized_df, feature_mapping)
    """
    if common_features is None:
        common_features = compute_cross_dataset_features(dataset_dirs)
    
    results = {}
    for dtype, data_dir in dataset_dirs.items():
        loader = dataset_registry.get_loader(dtype)
        raw_df = loader.load_raw(data_dir)
        harmonized_df, mapping = dataset_registry.harmonize_features(
            raw_df, dtype, common_features
        )
        results[dtype] = (harmonized_df, mapping)
    
    return results


def get_cross_dataset_report(
    results: Dict[DatasetType, Tuple[pd.DataFrame, FeatureMapping]]
) -> pd.DataFrame:
    """
    Generate a report comparing feature availability across datasets.
    
    Returns DataFrame with feature availability matrix.
    """
    all_features = set()
    for _, mapping in results.values():
        all_features.update(mapping.common_features)
        all_features.update(mapping.dataset_features)
    
    report_data = []
    for feature in sorted(all_features):
        row = {"Feature": feature}
        for dtype, (_, mapping) in results.items():
            row[f"{dtype.value}_available"] = feature in mapping.feature_mapping
            if feature in mapping.missing_features:
                row[f"{dtype.value}_status"] = "MISSING"
            elif feature in mapping.extra_features:
                row[f"{dtype.value}_status"] = "EXTRA"
            else:
                row[f"{dtype.value}_status"] = "OK"
        report_data.append(row)
    
    return pd.DataFrame(report_data)


# Example usage for adding new dataset loaders:
#
# class UNSWNB15Loader(BaseDatasetLoader):
#     def load_raw(self, data_dir: str) -> pd.DataFrame:
#         # Implementation for UNSW-NB15
#         pass
#     
#     def preprocess(self, df: pd.DataFrame) -> pd.DataFrame:
#         # UNSW-NB15 specific preprocessing
#         pass
#     
#     def get_attack_types(self) -> List[str]:
#         return ["Normal", "Generic", "Exploits", "Fuzzers", "DoS", "Reconnaissance", ...]
#     
#     def get_feature_names(self) -> List[str]:
#         return []
#
# # Register when ready:
# dataset_registry.register_loader(DatasetType.UNSW_NB15, UNSWNB15Loader())