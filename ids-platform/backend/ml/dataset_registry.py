"""
Dataset Abstraction Layer for Multi-Dataset IDS Evaluation

This module provides a unified interface for loading, preprocessing, and mapping
features across multiple intrusion detection datasets (CIC-IDS2017, UNSW-NB15,
CIC-IDS2018, TON-IoT, CICIoT2023) while maintaining a consistent feature space
for the existing ML pipeline.

Key concepts:
- DatasetConfig: Metadata and paths for each supported dataset
- FeatureMapper: Maps raw dataset features to the canonical PCA feature space
- DatasetRegistry: Registry of all supported datasets with compatibility info
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

from backend.ml.constants import ATTACK_MAP, ATTACK_KEYWORD_FALLBACK, UNKNOWN_ATTACK_LABEL
from backend.ml.preprocessing import (
    load_and_merge_dataset,
    clean_column_names,
    remove_duplicate_rows,
    handle_missing_and_infinite_values,
    drop_invariant_columns,
    optimize_memory_usage,
)
from backend.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class FeatureMapping:
    """Mapping from dataset raw features to canonical PCA features."""
    canonical_features: list[str]  # Expected PCA features (PC1..PCn)
    raw_to_canonical: dict[str, str]  # raw feature name -> canonical feature name
    unmapped_raw: list[str] = field(default_factory=list)  # raw features not mapped
    missing_canonical: list[str] = field(default_factory=list)  # canonical features not found in raw
    derived_features: dict[str, str] = field(default_factory=dict)  # canonical -> expression from raw


@dataclass
class DatasetConfig:
    """Configuration for a supported dataset."""
    name: str
    description: str
    data_dir: str
    label_column: str = "Label"
    attack_type_column: str = "Attack Type"
    filename_pattern: Optional[str] = None  # glob pattern for CSV files
    file_list: Optional[list[str]] = None  # explicit file list
    attack_map: Optional[dict[str, str]] = None  # raw label -> attack type
    keyword_fallback: Optional[list[tuple[str, str]]] = None
    unknown_label: str = "UNKNOWN"
    # Feature mapping (set after analysis)
    feature_mapping: Optional[FeatureMapping] = None
    # Compatibility
    compatible_with: list[str] = field(default_factory=list)  # other dataset names this is compatible with


class DatasetLoader(ABC):
    """Abstract base class for dataset-specific loading logic."""
    
    @abstractmethod
    def load_raw(self, data_dir: str) -> pd.DataFrame:
        """Load raw data from directory."""
        pass
    
    @abstractmethod
    def preprocess(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply dataset-specific preprocessing."""
        pass
    
    @abstractmethod
    def get_attack_type_distribution(self, df: pd.DataFrame) -> dict[str, int]:
        """Get attack type distribution."""
        pass


class CICIDS2017Loader(DatasetLoader):
    """Loader for CIC-IDS2017 dataset."""
    
    def __init__(self, config: DatasetConfig):
        self.config = config
    
    def load_raw(self, data_dir: str) -> pd.DataFrame:
        from backend.ml.preprocessing import load_and_merge_dataset
        filenames = self.config.file_list or None
        return load_and_merge_dataset(data_dir, filenames)
    
    def preprocess(self, df: pd.DataFrame) -> pd.DataFrame:
        df = clean_column_names(df)
        df = remove_duplicate_rows(df)
        df = handle_missing_and_infinite_values(df)
        
        # Map labels
        attack_map = self.config.attack_map or ATTACK_MAP
        keyword_fallback = self.config.keyword_fallback or ATTACK_KEYWORD_FALLBACK
        unknown_label = self.config.unknown_label
        
        label_col = self.config.label_column
        new_col = self.config.attack_type_column
        
        def _map_single_label(raw_label: str) -> str:
            if raw_label in self.config.attack_map:
                return self.config.attack_map[raw_label]
            lowered = raw_label.lower()
            for keyword, mapped_type in (self.config.keyword_fallback or []):
                if keyword in lowered:
                    return mapped_type
            return self.config.unknown_label
        
        df[self.config.attack_type_column] = df[self.config.label_column].astype(str).map(_map_single_label)
        
        n_unknown = int((df[self.config.attack_type_column] == self.config.unknown_label).sum())
        if n_unknown:
            unmatched_examples = (
                df.loc[df[self.config.attack_type_column] == self.config.unknown_label, self.config.label_column].unique()[:5]
            )
            logger.warning(
                "%d row(s) had a raw label with no known mapping (examples: %s)",
                n_unknown,
                list(unmatched_examples),
            )
        
        df = df.drop(columns=[self.config.label_column])
        
        df, _ = drop_invariant_columns(df)
        df = optimize_memory_usage(df)
        return df
    
    def get_attack_type_distribution(self, df: pd.DataFrame) -> dict[str, int]:
        return df[self.config.attack_type_column].value_counts().to_dict()


class UNSWNB15Loader(DatasetLoader):
    """Loader for UNSW-NB15 dataset."""
    
    def __init__(self, config: DatasetConfig):
        self.config = config
    
    def load_raw(self, data_dir: str) -> pd.DataFrame:
        # UNSW-NB15 typically has 4 CSV files
        files = self.config.file_list or [
            "UNSW-NB15_1.csv", "UNSW-NB15_2.csv",
            "UNSW-NB15_3.csv", "UNSW-NB15_4.csv"
        ]
        frames = []
        for filename in files:
            file_path = Path(data_dir) / filename
            if file_path.is_file():
                df = pd.read_csv(file_path)
                logger.info("Loaded '%s' -> %d rows, %d columns", filename, *df.shape)
                frames.append(df)
        if not frames:
            raise FileNotFoundError(f"No UNSW-NB15 files found in {data_dir}")
        merged = pd.concat(frames, ignore_index=True)
        logger.info("Merged UNSW-NB15 files -> %d rows, %d columns", *merged.shape)
        return merged
    
    def preprocess(self, df: pd.DataFrame) -> pd.DataFrame:
        df = clean_column_names(df)
        df = remove_duplicate_rows(df)
        df = handle_missing_and_infinite_values(df)
        
        # UNSW-NB15 label mapping
        # Original labels: Normal, Generic, Exploits, Fuzzers, DoS, Reconnaissance, 
        # Analysis, Backdoor, Shellcode, Worms
        attack_map = {
            "Normal": "BENIGN",
            "Generic": "Generic",
            "Exploits": "Exploit",
            "Fuzzers": "Fuzzer",
            "DoS": "DoS",
            "Reconnaissance": "Reconnaissance",
            "Analysis": "Analysis",
            "Backdoor": "Backdoor",
            "Shellcode": "Shellcode",
            "Worms": "Worms",
        }
        
        label_col = self.config.label_column
        new_col = self.config.attack_type_column
        
        def _map_single_label(raw_label: str) -> str:
            return attack_map.get(raw_label, "UNKNOWN")
        
        df[new_col] = df[label_col].astype(str).map(_map_single_label)
        
        n_unknown = int((df[new_col] == "UNKNOWN").sum())
        if n_unknown:
            unmatched = df.loc[df[new_col] == "UNKNOWN", label_col].unique()[:5]
            logger.warning("%d row(s) with unknown mapping (examples: %s)", n_unknown, list(unmatched))
        
        df = df.drop(columns=[label_col])
        df, _ = drop_invariant_columns(df)
        df = optimize_memory_usage(df)
        return df
    
    def get_attack_type_distribution(self, df: pd.DataFrame) -> dict[str, int]:
        return df[self.config.attack_type_column].value_counts().to_dict()


class DatasetRegistry:
    """Registry of all supported datasets with compatibility analysis."""
    
    def __init__(self):
        self._datasets: dict[str, DatasetConfig] = {}
        self._loaders: dict[str, type[DatasetLoader]] = {
            "CIC-IDS2017": CICIDS2017Loader,
            "UNSW-NB15": UNSWNB15Loader,
        }
        self._register_default_datasets()
    
    def _register_default_datasets(self):
        # CIC-IDS2017
        self.register(DatasetConfig(
            name="CIC-IDS2017",
            description="Canadian Institute for Cybersecurity IDS 2017 dataset",
            data_dir="data/raw/CIC-IDS2017",
            label_column="Label",
            attack_type_column="Attack Type",
            file_list=[
                "Monday-WorkingHours.pcap_ISCX.csv",
                "Tuesday-WorkingHours.pcap_ISCX.csv",
                "Wednesday-workingHours.pcap_ISCX.csv",
                "Thursday-WorkingHours-Morning-WebAttacks.pcap_ISCX.csv",
                "Thursday-WorkingHours-Afternoon-Infilteration.pcap_ISCX.csv",
                "Friday-WorkingHours-Morning.pcap_ISCX.csv",
                "Friday-WorkingHours-Afternoon-PortScan.pcap_ISCX.csv",
                "Friday-WorkingHours-Afternoon-DDos.pcap_ISCX.csv",
            ],
            attack_map=ATTACK_MAP,
            keyword_fallback=ATTACK_KEYWORD_FALLBACK,
            unknown_label=UNKNOWN_ATTACK_LABEL,
            compatible_with=["UNSW-NB15", "CIC-IDS2018"],
        ))
        
        # UNSW-NB15
        self.register(DatasetConfig(
            name="UNSW-NB15",
            description="UNSW-NB15 dataset from the Australian Centre for Cyber Security",
            data_dir="data/raw/UNSW-NB15",
            label_column="attack_cat",
            attack_type_column="Attack Type",
            file_list=["UNSW-NB15_1.csv", "UNSW-NB15_2.csv", "UNSW-NB15_3.csv", "UNSW-NB15_4.csv"],
            compatible_with=["CIC-IDS2017"],
        ))
        
        # CIC-IDS2018 (placeholder)
        self.register(DatasetConfig(
            name="CIC-IDS2018",
            description="CIC-IDS2018 dataset",
            data_dir="data/raw/CIC-IDS2018",
            compatible_with=["CIC-IDS2017"],
        ))
        
        # TON-IoT (placeholder)
        self.register(DatasetConfig(
            name="TON-IoT",
            description="ToN-IoT dataset for IoT network traffic",
            data_dir="data/raw/TON-IoT",
            compatible_with=["CIC-IDS2017"],
        ))
        
        # CICIoT2023 (placeholder)
        self.register(DatasetConfig(
            name="CICIoT2023",
            description="CIC IoT 2023 dataset",
            data_dir="data/raw/CICIoT2023",
            compatible_with=["CIC-IDS2017"],
        ))
    
    def register(self, config: DatasetConfig):
        self._datasets[config.name] = config
    
    def get(self, name: str) -> Optional[DatasetConfig]:
        return self._datasets.get(name)
    
    def get_loader(self, name: str) -> Optional[DatasetLoader]:
        config = self._datasets.get(name)
        if not config:
            return None
        loader_class = self._loaders.get(name)
        if not loader_class:
            return None
        return loader_class(config)
    
    def list_datasets(self) -> list[DatasetConfig]:
        return list(self._datasets.values())
    
    def analyze_feature_compatibility(self, dataset1: str, dataset2: str) -> FeatureMapping:
        """
        Analyze feature compatibility between two datasets.
        Returns a FeatureMapping showing how raw features map to canonical space.
        """
        config1 = self._datasets.get(dataset1)
        config2 = self._datasets.get(dataset2)
        
        if not config1 or not config2:
            raise ValueError(f"Dataset not found: {dataset1} or {dataset2}")
        
        # Load raw data from both datasets (sample for analysis)
        loader1 = self.get_loader(dataset1)
        loader2 = self.get_loader(dataset2)
        
        if not loader1 or not loader2:
            raise ValueError(f"Loader not available for {dataset1} or {dataset2}")
        
        # Sample data for analysis (first 1000 rows)
        try:
            df1 = loader1.load_raw(config1.data_dir).head(1000)
            df2 = loader2.load_raw(config2.data_dir).head(1000)
        except Exception as e:
            logger.warning("Could not load datasets for compatibility analysis: %s", e)
            return FeatureMapping(
                canonical_features=[],
                raw_to_canonical={},
                unmapped_raw=[],
                missing_canonical=[],
            )
        
        # Get numeric columns only
        num1 = df1.select_dtypes(include=[np.number]).columns.tolist()
        num2 = df2.select_dtypes(include=[np.number]).columns.tolist()
        
        # Find common features by name similarity
        common = set(num1) & set(num2)
        only1 = set(num1) - set(num2)
        only2 = set(num2) - set(num1)
        
        # Create mapping
        raw_to_canonical = {col: col for col in common}
        unmapped_raw = list(only1 | only2)
        missing_canonical = list(only2)  # features in dataset2 but not dataset1
        
        return FeatureMapping(
            canonical_features=sorted(common),
            raw_to_canonical=raw_to_canonical,
            unmapped_raw=unmapped_raw,
            missing_canonical=missing_canonical,
        )
    
    def generate_compatibility_report(self, base_dataset: str = "CIC-IDS2017") -> dict:
        """Generate a comprehensive compatibility report for all datasets vs base."""
        base_config = self._datasets.get(base_dataset)
        if not base_config:
            raise ValueError(f"Base dataset not found: {base_dataset}")
        
        report = {
            "base_dataset": base_dataset,
            "datasets": {},
        }
        
        for name, config in self._datasets.items():
            if name == base_dataset:
                continue
            
            compatibility = self.analyze_feature_compatibility(base_dataset, name)
            report["datasets"][name] = {
                "description": config.description,
                "compatible_with": config.compatible_with,
                "feature_mapping": {
                    "canonical_features_count": len(compatibility.canonical_features),
                    "raw_to_canonical_count": len(compatibility.raw_to_canonical),
                    "unmapped_raw_count": len(compatibility.unmapped_raw),
                    "missing_canonical_count": len(compatibility.missing_canonical),
                    "canonical_features": compatibility.canonical_features[:20],  # first 20
                    "unmapped_raw": compatibility.unmapped_raw[:20],
                    "missing_canonical": compatibility.missing_canonical[:20],
                }
            }
        
        return report


# Global registry instance
dataset_registry = DatasetRegistry()