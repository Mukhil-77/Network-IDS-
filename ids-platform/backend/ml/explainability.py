"""
Explainable AI for IDS alerts.

Generates local explanations for Random Forest and other tree-based models
using SHAP values, with PCA-aware feature attribution mapping back to
original flow features.

Research contribution: Explainable confidence-aware risk scoring.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from backend.utils.logger import get_logger

logger = get_logger(__name__)


# Try to import SHAP - optional dependency
try:
    import shap
    SHAP_AVAILABLE = True
except ImportError:
    SHAP_AVAILABLE = False
    logger.warning("SHAP not available. Install with: pip install shap")


@dataclass
class FeatureContribution:
    """Single feature contribution to prediction."""
    feature_name: str
    original_feature: str  # Original flow feature name (before PCA)
    contribution: float    # SHAP value (positive = increases attack probability)
    feature_value: float   # Actual value of the feature
    importance_rank: int   # Rank by absolute contribution
    direction: str         # "increases" or "decreases" attack probability


@dataclass
class ExplanationResult:
    """Complete explanation for a single prediction."""
    alert_id: str
    predicted_class: str
    confidence: float
    contributions: List[FeatureContribution]
    base_value: float      # Expected model output (E[f(x)])
    prediction_value: float  # Actual model output for this instance
    top_positive: List[FeatureContribution]  # Top features increasing attack prob
    top_negative: List[FeatureContribution]  # Top features decreasing attack prob
    explanation_text: str  # Human-readable summary
    feature_coverage_ratio: float = 1.0
    missing_features: List[str] = field(default_factory=list)
    model_version: str = ""
    timestamp: str = ""


class PCAFeatureMapper:
    """
    Maps PCA components back to original features for interpretability.
    
    Since the model operates on PCA components (PC1..PCn), we need to
    map SHAP values on PCs back to original flow features.
    """
    
    def __init__(
        self, 
        pca_components: np.ndarray,  # shape: (n_components, n_original_features)
        original_feature_names: List[str],
        pca_feature_names: List[str],  # e.g., ["PC1", "PC2", ...]
    ):
        self.pca_components = pca_components
        self.original_feature_names = original_feature_names
        self.pca_feature_names = pca_feature_names
        self.n_components = len(pca_feature_names)
        self.n_original = len(original_feature_names)
        
        # Validate dimensions
        assert pca_components.shape == (self.n_components, self.n_original), \
            f"PCA components shape mismatch: {pca_components.shape} vs ({self.n_components}, {self.n_original})"
    
    def map_shap_to_original(
        self, 
        shap_values_pca: np.ndarray,  # shape: (n_samples, n_components) or (n_components,)
        instance_pca: np.ndarray,      # PCA values for the instance
    ) -> np.ndarray:
        """
        Map SHAP values from PCA space back to original feature space.
        
        Uses the linear relationship: SHAP_original = SHAP_pca @ PCA_components
        
        For tree models on PCA features, we approximate the contribution
        of each original feature by projecting PCA SHAP values through
        the PCA loading matrix.
        
        Args:
            shap_values_pca: SHAP values for PCA components
            instance_pca: PCA-transformed feature values for this instance
            
        Returns:
            SHAP values for original features: (n_original_features,)
        """
        # Ensure 2D
        if shap_values_pca.ndim == 1:
            shap_values_pca = shap_values_pca.reshape(1, -1)
        
        # Map: original_contribution = sum_c (shap_c * pca_component_c)
        # This approximates how much each original feature contributed
        # to the PCA component's SHAP value
        original_shap = shap_values_pca @ self.pca_components  # (n_samples, n_original)
        
        return original_shap


class SHAPExplainer:
    """
    SHAP-based explainer for tree-based IDS models.
    
    Supports Random Forest, Decision Tree, XGBoost, LightGBM.
    Handles PCA-aware feature attribution.
    """
    
    def __init__(
        self,
        model: Any,
        feature_names: List[str],  # PCA feature names (PC1, PC2, ...)
        original_feature_names: Optional[List[str]] = None,
        pca_components: Optional[np.ndarray] = None,
        class_names: Optional[List[str]] = None,
    ):
        """
        Initialize SHAP explainer.
        
        Args:
            model: Fitted tree-based model (RF, DT, XGBoost, LGBM)
            feature_names: Feature names used by the model (PCA components)
            original_feature_names: Original flow feature names (before PCA)
            pca_components: PCA components matrix (n_components, n_original_features)
            class_names: Class labels for multi-class
        """
        if not SHAP_AVAILABLE:
            raise ImportError("SHAP not installed. Install with: pip install shap")
        
        self.model = model
        self.feature_names = feature_names
        self.original_feature_names = original_feature_names or feature_names
        self.pca_components = pca_components
        self.class_names = class_names
        
        # Create SHAP explainer
        self.explainer = self._create_explainer(model)
        
        # PCA mapper if available
        self.pca_mapper = None
        if pca_components is not None and original_feature_names:
            self.pca_mapper = PCAFeatureMapper(
                pca_components, original_feature_names, feature_names
            )
    
    def _create_explainer(self, model: Any) -> Any:
        """Create appropriate SHAP explainer for model type."""
        model_type = type(model).__name__
        
        if hasattr(model, 'estimators_') or 'RandomForest' in model_type or 'DecisionTree' in model_type:
            return shap.TreeExplainer(model)
        elif 'XGB' in model_type or 'XGBoost' in model_type:
            return shap.TreeExplainer(model)
        elif 'LGBM' in model_type or 'LightGBM' in model_type:
            return shap.TreeExplainer(model)
        else:
            # Fallback to KernelExplainer (slow but works for any model)
            logger.warning(f"Using KernelExplainer for {model_type} (slow)")
            return shap.KernelExplainer(model.predict_proba, None)  # Will need background data
    
    def explain_instance(
        self,
        instance: np.ndarray,  # PCA-transformed features
        instance_original: Optional[np.ndarray] = None,  # Original features
        class_idx: Optional[int] = None,
        top_k: int = 10,
    ) -> ExplanationResult:
        """
        Generate explanation for a single instance.
        
        Args:
            instance: PCA-transformed feature vector (n_components,)
            instance_original: Original feature values (n_original,) - optional
            class_idx: Class index to explain (None = predicted class)
            top_k: Number of top features to include in explanation
            
        Returns:
            ExplanationResult with contributions and human-readable text
        """
        # Ensure 2D
        if instance.ndim == 1:
            instance_2d = instance.reshape(1, -1)
        else:
            instance_2d = instance
        
        # Get SHAP values
        shap_values = self.explainer.shap_values(instance_2d)
        
        # Handle multi-class: shap_values is list of arrays per class
        if isinstance(shap_values, list):
            if class_idx is None:
                # Use predicted class
                proba = self.model.predict_proba(instance_2d)
                class_idx = int(np.argmax(proba[0]))
            shap_values_class = shap_values[class_idx][0]  # (n_features,)
            base_value = self.explainer.expected_value[class_idx]
        else:
            # Binary or single output
            shap_values_class = shap_values[0] if shap_values.ndim > 1 else shap_values
            base_value = self.explainer.expected_value
            if class_idx is None:
                class_idx = 0
        
        # Get prediction
        if hasattr(self.model, 'predict_proba'):
            proba = self.model.predict_proba(instance_2d)[0]
            predicted_class_idx = int(np.argmax(proba))
            confidence = float(proba[predicted_class_idx] * 100)
            predicted_class = self.class_names[predicted_class_idx] if self.class_names else str(predicted_class_idx)
        else:
            pred = self.model.predict(instance_2d)[0]
            predicted_class = self.class_names[pred] if self.class_names else str(pred)
            confidence = 100.0
        
        # Map SHAP to original features if PCA mapper available
        if self.pca_mapper and instance_original is not None:
            # Map PCA SHAP to original feature space
            original_shap = self.pca_mapper.map_shap_to_original(
                shap_values_class.reshape(1, -1), 
                instance.reshape(1, -1)
            )[0]  # (n_original,)
            
            contributions = self._build_contributions_original(
                original_shap, instance_original, top_k
            )
            feature_names = self.original_feature_names
        else:
            # Use PCA features directly
            contributions = self._build_contributions_pca(
                shap_values_class, instance, top_k
            )
            feature_names = self.feature_names
        
        # Build top positive/negative
        sorted_contrib = sorted(contributions, key=lambda c: abs(c.contribution), reverse=True)
        top_positive = [c for c in sorted_contrib if c.contribution > 0][:top_k]
        top_negative = [c for c in sorted_contrib if c.contribution < 0][:top_k]
        
        # Generate human-readable explanation
        explanation_text = self._generate_explanation_text(
            top_positive, top_negative, predicted_class, confidence
        )
        
        return ExplanationResult(
            alert_id="",  # Set by caller
            predicted_class=predicted_class,
            confidence=confidence,
            contributions=contributions,
            base_value=float(base_value) if np.isscalar(base_value) else float(base_value[0]),
            prediction_value=float(base_value + np.sum(shap_values_class)),
            top_positive=top_positive,
            top_negative=top_negative,
            explanation_text=explanation_text,
        )
    
    def _build_contributions_pca(
        self, 
        shap_values: np.ndarray, 
        instance: np.ndarray,
        top_k: int
    ) -> List[FeatureContribution]:
        """Build contributions from PCA features."""
        contributions = []
        
        for i, (feat_name, shap_val, feat_val) in enumerate(
            zip(self.feature_names, shap_values, instance)
        ):
            contributions.append(FeatureContribution(
                feature_name=feat_name,
                original_feature=feat_name,
                contribution=float(shap_val),
                feature_value=float(feat_val),
                importance_rank=0,  # Will be set after sorting
                direction="increases" if shap_val > 0 else "decreases",
            ))
        
        # Sort by absolute contribution
        contributions.sort(key=lambda c: abs(c.contribution), reverse=True)
        for rank, c in enumerate(contributions):
            c.importance_rank = rank + 1
        
        return contributions[:top_k]
    
    def _build_contributions_original(
        self,
        shap_values: np.ndarray,
        instance_original: np.ndarray,
        top_k: int
    ) -> List[FeatureContribution]:
        """Build contributions from original features."""
        contributions = []
        
        for i, (feat_name, shap_val, feat_val) in enumerate(
            zip(self.original_feature_names, shap_values, instance_original)
        ):
            contributions.append(FeatureContribution(
                feature_name=feat_name,
                original_feature=feat_name,
                contribution=float(shap_val),
                feature_value=float(feat_val),
                importance_rank=0,
                direction="increases" if shap_val > 0 else "decreases",
            ))
        
        contributions.sort(key=lambda c: abs(c.contribution), reverse=True)
        for rank, c in enumerate(contributions):
            c.importance_rank = rank + 1
        
        return contributions[:top_k]
    
    def _generate_explanation_text(
        self,
        top_positive: List[FeatureContribution],
        top_negative: List[FeatureContribution],
        predicted_class: str,
        confidence: float,
    ) -> str:
        """Generate human-readable explanation text."""
        lines = [
            f"Prediction: {predicted_class} (confidence: {confidence:.1f}%)",
            "",
            "Top features increasing attack probability:",
        ]
        
        for i, c in enumerate(top_positive[:5]):
            lines.append(
                f"  {i+1}. {c.feature_name}: {c.contribution:+.4f} "
                f"(value: {c.feature_value:.2f}) - increases {predicted_class} probability"
            )
        
        lines.append("")
        lines.append("Top features decreasing attack probability:")
        
        for i, c in enumerate(top_negative[:5]):
            lines.append(
                f"  {i+1}. {c.feature_name}: {c.contribution:+.4f} "
                f"(value: {c.feature_value:.2f}) - decreases {predicted_class} probability"
            )
        
        return "\n".join(lines)
    
    def explain_batch(
        self,
        instances: np.ndarray,
        instances_original: Optional[np.ndarray] = None,
        class_indices: Optional[List[int]] = None,
        top_k: int = 10,
    ) -> List[ExplanationResult]:
        """Generate explanations for multiple instances."""
        results = []
        for i, instance in enumerate(instances):
            class_idx = class_indices[i] if class_indices else None
            orig = instances_original[i] if instances_original is not None else None
            results.append(self.explain_instance(instance, orig, class_indices=class_idx, top_k=top_k))
        return results


def explain_alert(
    alert: Dict[str, Any],
    model: Any,
    feature_names: List[str],
    original_feature_names: Optional[List[str]] = None,
    pca_components: Optional[np.ndarray] = None,
    class_names: Optional[List[str]] = None,
    top_k: int = 10,
) -> ExplanationResult:
    """
    High-level function to explain an alert from the SOC pipeline.
    
    Args:
        alert: Alert dict with features
        model: Fitted model
        feature_names: PCA feature names
        original_feature_names: Original flow feature names
        pca_components: PCA components matrix
        class_names: Class labels
        top_k: Number of top features to explain
        
    Returns:
        ExplanationResult for the alert
    """
    # Extract features from alert
    features = alert.get("features", {})
    if not features:
        raise ValueError("Alert missing 'features' field")
    
    # Convert to array in correct order
    instance = np.array([features.get(f, 0.0) for f in feature_names])
    
    # Get original features if available
    instance_original = None
    if original_feature_names:
        instance_original = np.array([features.get(f, 0.0) for f in original_feature_names])
    
    # Create explainer
    explainer = SHAPExplainer(
        model=model,
        feature_names=feature_names,
        original_feature_names=original_feature_names,
        pca_components=pca_components,
        class_names=class_names,
    )
    
    # Get predicted class
    proba = model.predict_proba(instance.reshape(1, -1))[0]
    predicted_class_idx = int(np.argmax(proba))
    
    # Generate explanation
    result = explainer.explain_instance(
        instance=instance,
        instance_original=instance_original,
        class_idx=predicted_class_idx,
        top_k=10,
    )
    
    result.alert_id = alert.get("id", "")
    result.model_version = alert.get("model_version", "")
    result.timestamp = alert.get("timestamp", "")
    result.feature_coverage_ratio = alert.get("feature_coverage", 1.0)
    result.missing_features = alert.get("missing_features", [])
    
    return result


# Example usage:
#
# from backend.ml.explainability import explain_alert, SHAPExplainer
# from sklearn.ensemble import RandomForestClassifier
#
# # Load model and feature names
# model = RandomForestClassifier(...)
# feature_names = ["PC1", "PC2", ..., "PC35"]
# original_features = ["Flow Duration", "Total Fwd Packets", ...]
# pca_components = pca.components_  # shape (35, 70)
#
# # Explain an alert
# alert = {
#     "id": "alert_123",
#     "features": {"PC1": 0.5, "PC2": -0.3, ...},
#     "model_version": "v2",
# }
#
# result = explain_alert(
#     alert=alert,
#     model=model,
#     feature_names=feature_names,
#     original_feature_names=original_features,
#     pca_components=pca_components,
#     class_names=["BENIGN", "DoS", "DDoS", "Port Scan", "Bot", "Brute Force"]
# )
#
# print(result.explanation_text)
# for c in result.top_positive:
#     print(f"  + {c.feature_name}: {c.contribution:.4f}")