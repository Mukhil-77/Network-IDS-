"""
Confidence + Risk Scoring System

Implements a proper prediction confidence mechanism with separate:
- MODEL CONFIDENCE: how confident the classifier is (0-100%)
- RISK SCORE: security risk considering multiple factors (0-100)

Risk Score Factors:
- Attack probability
- Attack class severity
- Traffic behavior
- Frequency/repetition
- Source IP reputation
- Destination sensitivity
- Historical events
- Multiple alerts for same source
- Behavior persistence over time

Risk Levels:
0-20   LOW
21-40  GUARDED
41-60  MEDIUM
61-80  HIGH
81-100 CRITICAL
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional

import numpy as np
import pandas as pd

from backend.ml.unseen_detection import UnseenDetector
from backend.ml.severity import get_severity, SeverityLevel
from backend.threat_intelligence.reputation import reputation_registry, ThreatTag
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class RiskLevel(Enum):
    LOW = "LOW"
    GUARDED = "GUARDED"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class RiskFactors:
    """Individual risk factors contributing to the overall risk score."""
    attack_probability: float = 0.0           # 0-1, model's predicted attack probability
    attack_severity: float = 0.0              # 0-1, mapped from attack class severity
    traffic_behavior_score: float = 0.0       # 0-1, anomalous traffic patterns
    frequency_score: float = 0.0              # 0-1, repeated alerts from same source
    source_reputation: float = 0.0            # 0-1, threat intelligence reputation
    destination_sensitivity: float = 0.0      # 0-1, destination criticality
    historical_events: float = 0.0            # 0-1, historical alerts for this source
    persistence: float = 0.0                  # 0-1, behavior persistence over time
    multiple_alerts: float = 0.0              # 0-1, multiple related alerts
    
    def to_dict(self) -> dict:
        return {
            "attack_probability": self.attack_probability,
            "attack_severity": self.attack_severity,
            "traffic_behavior_score": self.traffic_behavior_score,
            "frequency_score": self.frequency_score,
            "source_reputation": self.source_reputation,
            "destination_sensitivity": self.destination_sensitivity,
            "historical_events": self.historical_events,
            "persistence": self.persistence,
            "multiple_alerts": self.multiple_alerts,
        }


@dataclass
class PredictionResult:
    """Complete prediction result with confidence, risk, and explanation."""
    predicted_class: str
    model_confidence: float              # 0-100, model's own confidence
    risk_score: int                      # 0-100, composite risk score
    risk_level: RiskLevel                # LOW/GUARDED/MEDIUM/HIGH/CRITICAL
    severity: str                        # LOW/MEDIUM/HIGH/CRITICAL
    risk_factors: RiskFactors
    is_unknown: bool                     # True if classified as unknown
    explanation: str                     # Human-readable explanation
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    flow_id: Optional[str] = None
    source_ip: Optional[str] = None
    destination_ip: Optional[str] = None
    source_port: Optional[int] = None
    destination_port: Optional[int] = None
    protocol: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "predicted_class": self.predicted_class,
            "model_confidence": self.model_confidence,
            "risk_score": self.risk_score,
            "risk_level": self.risk_level.value,
            "severity": self.severity,
            "risk_factors": self.risk_factors.to_dict(),
            "is_unknown": self.is_unknown,
            "explanation": self.explanation,
            "timestamp": self.timestamp.isoformat(),
            "flow_id": self.flow_id,
            "source_ip": self.source_ip,
            "destination_ip": self.destination_ip,
            "source_port": self.source_port,
            "destination_port": self.destination_port,
            "protocol": self.protocol,
        }


# Risk scoring weights (sum to 1.0)
RISK_WEIGHTS = {
    "attack_probability": 0.25,
    "attack_severity": 0.20,
    "traffic_behavior_score": 0.10,
    "frequency_score": 0.10,
    "source_reputation": 0.10,
    "destination_sensitivity": 0.10,
    "historical_events": 0.05,
    "persistence": 0.05,
    "multiple_alerts": 0.05,
}

# Attack class to severity mapping (0-1)
ATTACK_SEVERITY_MAP = {
    "BENIGN": 0.0,
    "BENIGN": 0.0,
    "DoS": 0.7,
    "DDoS": 0.9,
    "Port Scan": 0.4,
    "Port Scan": 0.4,
    "Brute Force": 0.6,
    "Web Attack - Brute Force": 0.7,
    "XSS": 0.5,
    "SQL Injection": 0.8,
    "Infiltration": 0.9,
    "Bot": 0.8,
    "Heartbleed": 0.6,
    "Exploit": 0.8,
    "Fuzzer": 0.4,
    "Reconnaissance": 0.3,
    "Analysis": 0.4,
    "Backdoor": 0.9,
    "Shellcode": 0.9,
    "Worms": 0.9,
    "UNKNOWN": 0.8,
    "Known Malicious": 0.9,
    "Suspicious": 0.6,
    "Trusted": 0.0,
    "Legitimate": 0.1,
}


def get_attack_severity(attack_type: str) -> float:
    """Get normalized severity score (0-1) for an attack type."""
    return ATTACK_SEVERITY_MAP.get(attack_type, 0.5)


class RiskScorer:
    """
    Computes risk scores from prediction results and contextual factors.
    
    The risk score is a weighted combination of multiple factors, normalized to 0-100.
    """
    
    def __init__(self, weights: dict[str, float] = None):
        self.weights = weights or RISK_WEIGHTS
        # Normalize weights to sum to 1
        total = sum(self.weights.values())
        self.weights = {k: v / sum(self.weights.values()) for k, v in self.weights.items()}
    
    def compute_risk_factors(
        self,
        attack_type: str,
        model_confidence: float,
        y_prob: np.ndarray = None,
        source_ip: str = None,
        destination_ip: str = None,
        source_port: int = None,
        destination_port: int = None,
        protocol: str = None,
        flow_features: dict = None,
        alert_history: list = None,
        db_session = None,
    ) -> RiskFactors:
        """
        Compute all risk factors for a prediction.
        """
        factors = RiskFactors()
        
        # 1. Attack probability (from model confidence)
        factors.attack_probability = min(1.0, max(0.0, 1.0 - (100 - 100) / 100))  # placeholder
        
        # Actually use model confidence
        if hasattr(self, '_last_confidence'):
            factors.attack_probability = self._last_confidence / 100.0
        else:
            factors.attack_probability = 0.5  # default
        
        # 2. Attack severity
        factors.attack_severity = get_attack_severity(y_prob is not None and "UNKNOWN" or "UNKNOWN")
        
        # 3. Traffic behavior score (from flow features)
        if flow_features:
            factors.traffic_behavior_score = self._compute_traffic_behavior(flow_features)
        
        # 4. Frequency score (repeated alerts from same source)
        if source_ip:
            factors.frequency_score = self._compute_frequency_score(source_ip)
        
        # 5. Source reputation
        if source_ip:
            factors.source_reputation = self._get_source_reputation(source_ip)
        
        # 6. Destination sensitivity
        if destination_ip:
            factors.destination_sensitivity = self._get_destination_sensitivity(destination_ip)
        
        # 5. Historical events
        if source_ip:
            factors.historical_events = self._get_historical_events(source_ip)
        
        # 7. Persistence
        if source_ip and alert_history:
            factors.persistence = self._compute_persistence(alert_history)
        
        # 8. Multiple alerts
        if source_ip and alert_history:
            factors.multiple_alerts = self._compute_multiple_alerts(alert_history)
        
        return factors
    
    def _compute_traffic_behavior(self, flow_features: dict) -> float:
        """Compute traffic behavior anomaly score from flow features."""
        # Simple heuristic: check for unusual feature values
        score = 0.0
        # Example: very high packet rate, unusual packet sizes, etc.
        # This would be customized based on domain knowledge
        return min(1.0, score)
    
    def _compute_frequency_score(self, source_ip: str) -> float:
        """Compute frequency score based on alert history for this source."""
        # Would query database for recent alerts from this source
        # Placeholder: returns 0.0
        return 0.0
    
    def _get_source_reputation(self, source_ip: str) -> float:
        """Get reputation score from threat intelligence."""
        # Query threat intelligence
        try:
            # This would use the reputation_registry
            # For now, return 0.0 (neutral)
            return 0.0
        except:
            return 0.0
    
    def _get_destination_sensitivity(self, destination_ip: str) -> float:
        """Get destination sensitivity score."""
        # Check if destination is a critical asset
        # Placeholder
        return 0.0
    
    def _get_historical_events(self, source_ip: str) -> float:
        """Get historical event count for source."""
        return 0.0
    
    def _compute_persistence(self, alert_history: list) -> float:
        """Compute behavior persistence score."""
        return 0.0
    
    def _compute_multiple_alerts(self, alert_history: list) -> float:
        """Compute multiple alerts score."""
        return min(1.0, len(alert_history) / 10.0)


class ConfidenceRiskScorer:
    """
    Main class for computing confidence, risk, and generating prediction results.
    """
    
    def __init__(
        self,
        model: Any,
        unseen_detector: UnseenDetector = None,
        risk_scorer: RiskScorer = None,
        severity_map: dict[str, str] = None,
    ):
        self.model = model
        self.unseen_detector = unseen_detector or UnseenDetector(model, [])
        self.risk_scorer = risk_scorer or RiskScorer()
        self.severity_map = severity_map or {}
        
        # Store last confidence for risk computation
        self._last_confidence = 0.0
    
    def predict(self, X: pd.DataFrame, flow_context: dict = None) -> list[PredictionResult]:
        """
        Make predictions with full confidence, risk scoring, and explanations.
        
        Args:
            X: Feature matrix (PCA-transformed features)
            flow_context: Optional dict with flow context (source_ip, destination_ip, etc.)
            
        Returns:
            List of PredictionResult with full confidence, risk, and explanation.
        """
        # Get model predictions
        predictions = self.model.predict(X)
        probabilities = self.model.predict_proba(X) if hasattr(self.model, "predict_proba") else None
        
        results = []
        for i, pred in enumerate(predictions):
            # Get model confidence (max probability)
            if probabilities is not None:
                max_prob = probabilities[i].max()
                confidence = float(max_prob * 100)
            else:
                confidence = 50.0  # default if no probabilities
            
            # Store for risk scoring
            self._last_confidence = confidence / 100.0
            
            # Get risk factors
            flow_context = flow_context or {}
            risk_factors = self._compute_risk_factors(
                predicted_class=pred,
                confidence=confidence,
                flow_context=flow_context,
            )
            
            # Compute risk score
            risk_score = self._compute_risk_score(risk_factors)
            risk_level = self._score_to_risk_level(risk_score)
            
            # Get severity
            severity = self._get_severity(pred)
            
            # Check if unknown
            is_unknown = self._is_unknown(pred, probabilities[i] if probabilities is not None else None)
            
            # Generate explanation
            explanation = self._generate_explanation(pred, confidence, risk_factors)
            
            result = PredictionResult(
                predicted_class=pred,
                model_confidence=confidence,
                risk_score=risk_score,
                risk_level=risk_level,
                severity=severity,
                risk_factors=risk_factors,
                is_unknown=is_unknown,
                explanation=self._generate_explanation(pred, confidence, risk_factors),
            )
            
            # Add flow context if provided
            if flow_context:
                result.flow_id = flow_context.get("flow_id")
                result.source_ip = flow_context.get("source_ip")
                result.destination_ip = flow_context.get("destination_ip")
                result.source_port = flow_context.get("source_port")
                result.destination_port = flow_context.get("destination_port")
                result.protocol = flow_context.get("protocol")
            
            results.append(result)
        
        return results
    
    def _compute_risk_factors(self, predicted_class: str, confidence: float, flow_context: dict) -> RiskFactors:
        """Compute all risk factors."""
        factors = RiskFactors()
        
        # 1. Attack probability (1 - normalized confidence for attacks, 1 - confidence for benign)
        if predicted_class == "BENIGN" or predicted_class == "UNKNOWN":
            factors.attack_probability = 1.0 - (confidence / 100.0)
        else:
            factors.attack_probability = confidence / 100.0
        
        # 2. Attack severity
        factors.attack_severity = get_attack_severity(predicted_class)
        
        # 3. Traffic behavior (placeholder - would use flow features)
        factors.traffic_behavior_score = 0.3  # default
        
        # 4. Frequency score (placeholder)
        factors.frequency_score = 0.2
        
        # 5. Source reputation
        factors.source_reputation = 0.0
        
        # 6. Destination sensitivity
        factors.destination_sensitivity = 0.0
        
        # 7. Historical events
        factors.historical_events = 0.0
        
        # 8. Persistence
        factors.persistence = 0.0
        
        # 9. Multiple alerts
        factors.multiple_alerts = 0.0
        
        return factors
    
    def _compute_risk_score(self, factors: RiskFactors) -> int:
        """Compute composite risk score (0-100) from weighted factors."""
        score = 0.0
        for factor_name, weight in RISK_WEIGHTS.items():
            factor_value = getattr(factors, factor_name, 0.0)
            score += weight * factor_value
        return int(min(100, max(0, score * 100)))
    
    def _score_to_risk_level(self, score: int) -> RiskLevel:
        """Convert risk score to risk level."""
        if score <= 20:
            return RiskLevel.LOW
        elif score <= 40:
            return RiskLevel.GUARDED
        elif score <= 60:
            return RiskLevel.MEDIUM
        elif score <= 80:
            return RiskLevel.HIGH
        else:
            return RiskLevel.CRITICAL
    
    def _get_severity(self, attack_type: str) -> str:
        """Get severity level for attack type."""
        severity_map = {
            "BENIGN": "LOW",
            "UNKNOWN": "HIGH",
            "DoS": "HIGH",
            "DDoS": "CRITICAL",
            "Port Scan": "MEDIUM",
            "Brute Force": "HIGH",
            "Web Attack - Brute Force": "HIGH",
            "XSS": "MEDIUM",
            "SQL Injection": "CRITICAL",
            "Infiltration": "CRITICAL",
            "Bot": "HIGH",
            "Heartbleed": "HIGH",
            "Exploit": "CRITICAL",
            "Fuzzer": "MEDIUM",
            "Reconnaissance": "LOW",
            "Analysis": "LOW",
            "Backdoor": "CRITICAL",
            "Shellcode": "CRITICAL",
            "Worms": "CRITICAL",
            "UNKNOWN": "HIGH",
            "Known Malicious": "CRITICAL",
            "Suspicious": "HIGH",
            "Trusted": "LOW",
            "Legitimate": "LOW",
        }
        return severity_map.get(predicted_class, "MEDIUM")
    
    def _is_unknown(self, predicted_class: str, probabilities: np.ndarray = None) -> bool:
        """Determine if prediction should be classified as unknown."""
        # Use unseen detector if available
        if self.unseen_detector:
            pred = self.unseen_detector.predict(pd.DataFrame([{}])[0])  # placeholder
            return pred.is_unknown
        return False
    
    def _generate_explanation(self, predicted_class: str, confidence: float, risk_factors: RiskFactors) -> str:
        """Generate human-readable explanation for the prediction."""
        parts = []
        
        parts.append(f"Classified as {predicted_class} with {confidence:.1f}% confidence.")
        
        if risk_factors.attack_severity > 0.7:
            parts.append(f"High severity attack type ({predicted_class}).")
        elif risk_factors.attack_severity > 0.4:
            parts.append(f"Moderate severity attack type ({predicted_class}).")
        
        if risk_factors.source_reputation > 0.5:
            parts.append("Source IP has poor reputation.")
        
        if risk_factors.frequency_score > 0.5:
            parts.append("Repeated alerts from this source.")
        
        if risk_factors.multiple_alerts > 0.5:
            parts.append("Multiple related alerts detected.")
        
        if risk_factors.persistence > 0.5:
            parts.append("Persistent suspicious behavior over time.")
        
        if risk_factors.attack_probability > 0.8:
            parts.append("High attack probability.")
        
        return " ".join(parts)


# Global instance getter
def create_confidence_risk_scorer(model: Any, unseen_detector: Any = None) -> ConfidenceRiskScorer:
    """Factory function to create a ConfidenceRiskScorer with default settings."""
    return ConfidenceRiskScorer(model=model, unseen_detector=None)


if __name__ == "__main__":
    print("Risk scoring module loaded successfully")