"""
Explainable AI (SHAP) Integration for IDS Predictions

Provides SHAP-based explanations for model predictions, showing:
- Top contributing features
- Feature contribution direction (positive/negative)
- Prediction explanation in human-readable format
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Callable

import numpy as np
import pandas as pd

from backend.ml.predictor import get_predictor
from backend.ml.artifacts import load_model_bundle
from backend.utils.logger import get_logger

logger = get_logger(__name__)

try:
    import shap
    SHAP_AVAILABLE = True
except ImportError:
    SHAP_AVAILABLE = False
    logger.warning("SHAP not available. Install with: pip install shap")


@dataclass
class SHAPExplanation:
    """SHAP-based explanation for a single prediction."""
    predicted_class: str
    confidence: float
    top_features: list[dict]  # [{"feature": "PC1", "value": 0.5, "shap_value": 0.15, "impact": "positive"}]
    base_value: float
    prediction_value: float
    feature_names: list[str]
    
    def to_dict(self) -> dict:
        return {
            "predicted_class": self.predicted_class,
            "confidence": self.confidence,
            "top_features": self.top_features,
            "base_value": self.base_value,
            "prediction_value": self.prediction_value,
            "feature_names": self.feature_names,
        }


@dataclass
class GlobalSHAPSummary:
    """Global SHAP feature importance summary."""
    feature_importance: list[dict]  # [{"feature": "PC1", "mean_abs_shap": 0.12, "mean_shap": 0.05}]
    total_samples: int
    
    def to_dict(self) -> dict:
        return {
            "feature_importance": self.feature_importance,
            "total_samples": self.total_samples,
        }


class SHAPExplainer:
    """
    SHAP-based explainer for IDS model predictions.
    
    Supports TreeSHAP (for tree-based models) and KernelSHAP (fallback).
    """
    
    def __init__(self, model: Any, feature_names: list[str], background_data: pd.DataFrame = None):
        """
        Initialize SHAP explainer.
        
        Args:
            model: Trained sklearn model (RandomForest, DecisionTree, etc.)
            feature_names: List of feature names (PCA components PC1..PCn)
            background_data: Background dataset for SHAP (optional, for KernelSHAP)
        """
        self.model = model
        self.feature_names = feature_names
        self.background_data = background_data
        self._explainer = None
        self._init_explainer()
    
    def _init_explainer(self):
        """Initialize appropriate SHAP explainer based on model type."""
        if not SHAP_AVAILABLE:
            logger.warning("SHAP not available, explanations will be unavailable")
            return
        
        try:
            # Try TreeSHAP for tree-based models
            if hasattr(self.model, 'tree_') or hasattr(self.model, 'estimators_'):
                # RandomForest, DecisionTree, etc.
                self._explainer = shap.TreeExplainer(self.model)
                logger.info("Initialized TreeExplainer")
            else:
                # Fallback to KernelExplainer (slower but model-agnostic)
                logger.warning("Model not tree-based, using KernelExplainer (slower)")
                # Need background data for KernelExplainer
                if self.background_data is not None and len(self.background_data) > 0:
                    # Sample background data for efficiency
                    sample_size = min(100, len(self.background_data))
                    bg_sample = self.background_data.sample(min(sample_size, len(self.background_data)), random_state=42)
                    self._explainer = shap.KernelExplainer(
                        self.model.predict_proba, 
                        bg_sample
                    )
                    logger.info("Initialized KernelExplainer with %d background samples", len(bg_sample))
                else:
                    logger.warning("No background data for KernelExplainer, explanations unavailable")
        except Exception as e:
            logger.warning(f"Failed to initialize SHAP explainer: {e}")
            self._explainer = None
    
    def explain_instance(
        self, 
        instance: pd.Series | np.ndarray, 
        class_names: list[str] = None,
        top_k: int = 10,
        predicted_class: str = None,
    ) -> SHAPExplanation:
        """
        Generate SHAP explanation for a single instance.
        
        Args:
            instance: Single instance features (PCA components)
            class_names: List of class names
            top_k: Number of top features to include
            predicted_class: The predicted class for this instance (to select correct SHAP values)
            
        Returns:
            SHAPExplanation object
        """
        if not SHAP_AVAILABLE or self._explainer is None:
            return self._fallback_explanation(instance, top_k)
        
        # Convert to array
        if isinstance(instance, pd.Series):
            instance_array = instance.values.reshape(1, -1)
        else:
            instance_array = np.array(instance).reshape(1, -1)
        
        try:
            # Get SHAP values
            shap_values = self._explainer.shap_values(instance_array)
            
            # Handle multi-class output
            if isinstance(shap_values, list):
                # Multi-class: shap_values is list of arrays, one per class
                # Determine which class to use
                if predicted_class is not None and hasattr(self.model, 'classes_'):
                    class_names_model = [str(c) for c in self.model.classes_]
                    if predicted_class in class_names_model:
                        class_idx = class_names_model.index(predicted_class)
                    else:
                        class_idx = 0
                else:
                    class_idx = 0
                shap_vals = shap_values[class_idx][0] if shap_values else np.zeros(len(self.feature_names))
            else:
                # Binary or single output
                shap_vals = shap_values[0] if shap_values.ndim > 1 else shap_values
            
            # Get base value
            if hasattr(self._explainer, 'expected_value'):
                base_value = self._explainer.expected_value
                if isinstance(base_value, (list, np.ndarray)):
                    base_value = base_value[0] if len(base_value) > 0 else 0.0
            else:
                base_value = 0.0
            
            # Get prediction value (sum of SHAP values + base)
            prediction_value = float(base_value + np.sum(shap_vals))
            
            # Ensure shap_vals is 1D
            shap_vals = np.array(shap_vals).flatten()
            
            # Get top features by absolute SHAP value
            feature_shap = list(zip(self.feature_names, shap_vals))
            feature_shap_sorted = sorted(feature_shap, key=lambda x: abs(x[1]), reverse=True)
            
            top_features = []
            for feat_name, shap_val in feature_shap_sorted[:top_k]:
                shap_val_float = float(shap_val)
                top_features.append({
                    "feature": feat_name,
                    "shap_value": shap_val_float,
                    "impact": "positive" if shap_val_float > 0 else "negative",
                    "magnitude": float(abs(shap_val_float)),
                })
            
            return SHAPExplanation(
                predicted_class="",  # Will be set by caller
                confidence=0.0,
                top_features=top_features,
                base_value=float(base_value),
                prediction_value=float(prediction_value),
                feature_names=self.feature_names,
            )
            
        except Exception as e:
            logger.warning(f"SHAP explanation failed: {e}")
            return self._fallback_explanation(instance, top_k)
    
    def _fallback_explanation(self, instance: pd.Series | np.ndarray, top_k: int) -> SHAPExplanation:
        """Fallback explanation when SHAP is not available."""
        if isinstance(instance, pd.Series):
            feat_vals = instance.values
        else:
            feat_vals = instance.flatten()
        
        # Use absolute feature values as proxy for importance
        feat_importance = list(zip(self.feature_names, feat_vals))
        feat_sorted = sorted(feat_importance, key=lambda x: abs(x[1]), reverse=True)
        
        top_features = []
        for feat_name, val in feat_sorted[:top_k]:
            top_features.append({
                "feature": feat_name,
                "value": float(val),
                "shap_value": 0.0,
                "impact": "unknown",
                "magnitude": float(abs(val)),
            })
        
        return SHAPExplanation(
            predicted_class="",
            confidence=0.0,
            top_features=top_features,
            base_value=0.0,
            prediction_value=0.0,
            feature_names=self.feature_names,
        )
    
    def explain_batch(
        self, 
        instances: pd.DataFrame, 
        top_k: int = 10
    ) -> list[SHAPExplanation]:
        """Generate explanations for a batch of instances."""
        explanations = []
        for _, row in instances.iterrows():
            exp = self.explain_instance(row, top_k=top_k)
            explanations.append(exp)
        return explanations
    
    def compute_global_importance(
        self, 
        background_data: pd.DataFrame, 
        max_samples: int = 1000
    ) -> 'GlobalSHAPSummary':
        """
        Compute global feature importance from a sample of data.
        
        Args:
            background_data: Dataset to compute importance on
            max_samples: Maximum number of samples to use
            
        Returns:
            GlobalSHAPSummary with feature importance rankings
        """
        if not SHAP_AVAILABLE or self._explainer is None:
            return GlobalSHAPSummary(feature_importance=[], total_samples=0)
        
        sample = background_data.sample(min(max_samples, len(background_data)))
        
        try:
            shap_values = self._explainer.shap_values(sample)
            
            if isinstance(shap_values, list):
                # Multi-class: average across classes
                mean_shap = np.mean([np.abs(sv).mean(axis=0) for sv in shap_values], axis=0)
            else:
                mean_shap = np.abs(shap_values).mean(axis=0)
            
            importance = list(zip(self.feature_names, mean_shap))
            importance_sorted = sorted(importance, key=lambda x: x[1], reverse=True)
            
            feature_importance = [
                {
                    "feature": name,
                    "mean_abs_shap": float(val),
                    "mean_shap": 0.0,  # would need signed values
                }
                for name, val in importance_sorted
            ]
            
            return GlobalSHAPSummary(
                feature_importance=feature_importance,
                total_samples=len(self.background_data),
            )
        except Exception as e:
            logger.warning(f"Global SHAP importance failed: {e}")
            return GlobalSHAPSummary(feature_importance=[], total_samples=0)


def create_shap_explainer(
    model_path: str = None,
    model: Any = None,
    feature_names: list[str] = None,
    background_data: pd.DataFrame = None,
) -> SHAPExplainer:
    """
    Factory function to create SHAP explainer from model path or model object.
    
    Args:
        model_path: Path to model version directory (e.g., "models/v4")
        model: Pre-loaded model object (optional)
        feature_names: List of feature names
        background_data: Background data for KernelSHAP
        
    Returns:
        SHAPExplainer instance
    """
    if model is None and model_path:
        # Load from artifacts
        from backend.ml.artifacts import load_model_bundle
        import os
        bundle = load_model_bundle(model_path)
        model = bundle["model"]
        feature_names = feature_names or bundle.get("feature_names", [])
        
        # Try to load background data from training data
        background_data = None
        try:
            from backend.ml.preprocessing import preprocess_dataset
            import os
            
            # Load raw data and apply the same feature engineering as training
            data_dir = "data/raw"
            if os.path.exists(data_dir):
                # Use the scaler and PCA from the bundle
                bundle = load_model_bundle(model_path)
                scaler = bundle["scaler"]
                pca = bundle["pca"]
                feature_names = bundle["feature_names"]
                
                # Load raw data
                df = preprocess_dataset(data_dir)
                
                # Check numeric columns
                numeric_cols = df.select_dtypes(include=[np.number]).columns
                df_numeric = df[numeric_cols]
                
                # Apply the same scaler and PCA from the bundle
                X_scaled = scaler.transform(df_numeric)
                X_pca = pca.transform(X_scaled)
                
                # Create DataFrame with PCA feature names (ONLY the PCA features, no target)
                pca_df = pd.DataFrame(X_pca, columns=feature_names)
                
                # Sample for background (ONLY features, no target column)
                background_data = pca_df.sample(min(200, len(pca_df)), random_state=42)
                logger.info(f"Loaded {len(background_data)} background samples for SHAP (features only)")
        except Exception as e:
            import traceback
            logger.warning(f"Could not load background data: {e}")
            traceback.print_exc()
        
        return SHAPExplainer(
            model=model,
            feature_names=feature_names or [],
            background_data=background_data,
        )
    
    if model is None:
        raise ValueError("Either model or model_path must be provided")
    
    return SHAPExplainer(
        model=model,
        feature_names=feature_names or [],
        background_data=background_data,
    )
    
    if model is None:
        raise ValueError("Either model or model_path must be provided")
    
    return SHAPExplainer(
        model=model,
        feature_names=feature_names or [],
        background_data=background_data,
    )


def generate_explanation_text(shap_exp: SHAPExplanation, predicted_class: str, confidence: float) -> str:
    """
    Generate human-readable explanation from SHAP explanation.
    
    Returns:
        Human-readable explanation string
    """
    parts = []
    parts.append(f"Classified as {shap_exp.predicted_class or 'UNKNOWN'} with {shap_exp.confidence:.1f}% confidence.")
    
    if shap_exp.top_features:
        parts.append("Top contributing factors:")
        for feat in shap_exp.top_features[:5]:
            direction = "increased" if feat["impact"] == "positive" else "decreased"
            parts.append(
                f"  - {feat['feature']}: {feat['value']:.3f} ({direction} likelihood)"
            )
    
    return " ".join([str(p) for p in parts])


def format_explanation_for_ui(shap_exp: SHAPExplanation) -> dict:
    """
    Format SHAP explanation for UI display.
    
    Returns dict suitable for frontend rendering.
    """
    return {
        "top_features": [
            {
                "name": f["feature"],
                "value": f.get("value", 0),
                "shap_value": f["shap_value"],
                "impact": f["impact"],
                "bar_length": min(100, max(0, abs(f["shap_value"]) * 100)),  # for progress bar
                "color": "green" if f["impact"] == "positive" else "red" if f["impact"] == "negative" else "gray",
            }
            for f in shap_exp.top_features
        ],
        "base_value": shap_exp.base_value,
        "prediction_value": shap_exp.prediction_value,
    }


if __name__ == "__main__":
    print("SHAP explainer module loaded successfully")
    if SHAP_AVAILABLE:
        print("SHAP is available")
    else:
        print("SHAP not available - install with: pip install shap")