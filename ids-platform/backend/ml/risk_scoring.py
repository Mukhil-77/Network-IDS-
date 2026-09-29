"""
Risk scoring for IDS alerts.

Combines calibrated model confidence, feature coverage, threat intelligence,
severity, repetition, and asset context into a unified 0-100 risk score.

Risk tiers:
- 0-20:   LOW
- 21-40:  GUARDED
- 41-60:  MEDIUM
- 61-80:  HIGH
- 81-100: CRITICAL

Research contribution: Coverage-aware calibrated confidence -> risk score -> explainable alert prioritization.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from backend.ml.calibration import ConfidenceCalibrator
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class RiskTier(Enum):
    """Risk score tiers."""
    LOW = "LOW"
    GUARDED = "GUARDED"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
    
    @classmethod
    def from_score(cls, score: float) -> "RiskTier":
        if score <= 20:
            return cls.LOW
        elif score <= 40:
            return cls.GUARDED
        elif score <= 60:
            return cls.MEDIUM
        elif score <= 80:
            return cls.HIGH
        else:
            return cls.CRITICAL


class SeverityLevel(Enum):
    """Attack severity levels."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
    
    @classmethod
    def from_string(cls, s: str) -> "SeverityLevel":
        s_upper = s.upper()
        if s_upper in [e.value for e in cls]:
            return cls(s_upper)
        # Map legacy severity strings
        mapping = {
            "LOW": cls.LOW,
            "MEDIUM": cls.MEDIUM,
            "HIGH": cls.HIGH,
            "CRITICAL": cls.CRITICAL,
            "LOW_RISK": cls.LOW,
            "GUARDED": cls.MEDIUM,
        }
        return mapping.get(s_upper, cls.MEDIUM)
    
    def to_weight(self) -> float:
        """Convert severity to risk weight (0-1)."""
        weights = {
            SeverityLevel.LOW: 0.2,
            SeverityLevel.MEDIUM: 0.6,
            SeverityLevel.HIGH: 0.8,
            SeverityLevel.CRITICAL: 1.0,
        }
        return weights.get(self, 0.5)


@dataclass
class ThreatIntelContext:
    """Threat intelligence context for risk scoring."""
    tag: str  # "Known Malicious", "Suspicious", "Unknown", "Trusted"
    source: str
    confidence: float  # 0-100
    notes: str = ""
    is_malicious: bool = False
    is_trusted: bool = False
    
    def __post_init__(self):
        self.is_malicious = self.tag in ("Known Malicious", "Suspicious")
        self.is_trusted = self.tag == "Trusted"


@dataclass
class AssetContext:
    """Asset/asset importance context."""
    asset_id: str
    asset_type: str  # "server", "workstation", "database", "network_device", etc.
    importance: str  # "low", "medium", "high", "critical"
    zone: str = "internal"  # "internal", "dmz", "external", "cloud"
    
    def to_weight(self) -> float:
        weights = {
            "low": 0.5,
            "medium": 0.75,
            "high": 1.0,
            "critical": 1.25,
        }
        return weights.get(self.importance.lower(), 0.75)


@dataclass
class AlertContext:
    """Full context for risk scoring an alert."""
    # Model prediction
    predicted_class: str
    raw_confidence: float  # 0-100, uncalibrated model probability
    calibrated_confidence: Optional[float] = None  # 0-100, calibrated
    
    # Feature coverage
    feature_coverage_ratio: float = 1.0  # 0-1, fraction of features available
    missing_features: List[str] = field(default_factory=list)
    
    # Threat intelligence
    threat_intel: Optional[ThreatIntelContext] = None
    
    # Asset context
    source_asset: Optional[AssetContext] = None
    target_asset: Optional[AssetContext] = None
    
    # Temporal context
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    event_count: int = 1
    related_alerts: int = 0  # Number of related alerts in time window
    
    # Network context
    source_ip: str = ""
    dest_ip: str = ""
    source_port: int = 0
    dest_port: int = 0
    protocol: str = ""
    
    # Model metadata
    model_version: str = ""
    processing_time_ms: float = 0.0


@dataclass
class RiskScoreResult:
    """Result of risk scoring."""
    risk_score: float  # 0-100
    risk_tier: RiskTier
    components: Dict[str, float]  # breakdown of score components
    reasoning: List[str]  # human-readable explanations
    confidence: float  # calibrated confidence 0-100
    severity: SeverityLevel
    recommended_action: str
    requires_human_review: bool


class RiskScorer:
    """
    Computes unified risk score for IDS alerts.
    
    Combines multiple signals into a single 0-100 risk score:
    - Calibrated model confidence (30%)
    - Feature coverage (10%)
    - Attack severity (20%)
    - Threat intelligence (15%)
    - Repetition/persistence (15%)
    - Asset importance (10%)
    """
    
    # Default weights (sum to 1.0)
    DEFAULT_WEIGHTS = {
        "confidence": 0.30,
        "coverage": 0.10,
        "severity": 0.20,
        "threat_intel": 0.15,
        "repetition": 0.15,
        "asset_importance": 0.10,
    }
    
    def __init__(
        self,
        weights: Optional[Dict[str, float]] = None,
        confidence_thresholds: Optional[Dict[str, float]] = None,
    ):
        self.weights = weights or self.DEFAULT_WEIGHTS.copy()
        self.confidence_thresholds = confidence_thresholds or {
            "low": 0.50,
            "medium": 0.70,
            "high": 0.85,
            "critical": 0.95,
        }
        # Normalize weights
        total = sum(self.weights.values())
        self.weights = {k: v / total for k, v in self.weights.items()}
        
        # Risk tier boundaries
        self.tier_boundaries = {
            RiskTier.CRITICAL: 80,
            RiskTier.HIGH: 60,
            RiskTier.MEDIUM: 40,
            RiskTier.GUARDED: 20,
            RiskTier.LOW: 0,
        }
    
    def compute_risk_score(self, context: AlertContext) -> RiskScoreResult:
        """
        Compute unified risk score for an alert.
        
        Args:
            context: Full alert context
            
        Returns:
            RiskScoreResult with score, tier, components, and reasoning
        """
        components = {}
        reasoning = []
        
        # 1. Calibrated confidence (30%)
        confidence = context.calibrated_confidence if context.calibrated_confidence is not None \
            else context.raw_confidence
        confidence_norm = confidence / 100.0
        components["confidence"] = confidence_norm * 100 * self.weights["confidence"]
        reasoning.append(
            f"Model confidence: {confidence:.1f}% "
            f"({'calibrated' if context.calibrated_confidence else 'raw'})"
        )
        
        # 2. Feature coverage (10%)
        coverage = max(0.0, min(1.0, context.feature_coverage_ratio))
        coverage_penalty = (1.0 - coverage) * 100 * self.weights["coverage"]
        components["coverage"] = coverage * 100 * self.weights["coverage"]
        if coverage < 1.0:
            reasoning.append(
                f"Feature coverage: {coverage:.1%} "
                f"({len(context.missing_features)} features missing)"
            )
        
        # 3. Severity (20%)
        severity = SeverityLevel.from_string(context.predicted_class) \
            if hasattr(context, 'severity') else SeverityLevel.MEDIUM
        severity_weight = severity.to_weight()
        components["severity"] = severity_weight * 100 * self.weights["severity"]
        reasoning.append(f"Attack severity: {severity.value}")
        
        # 4. Threat intelligence (15%)
        ti_score = 0.5  # neutral default
        if context.threat_intel:
            ti = context.threat_intel
            if ti.is_malicious:
                ti_score = 0.8 + (ti.confidence / 100) * 0.2  # 0.8-1.0
                reasoning.append(f"Threat intel: {ti.tag} (confidence {ti.confidence:.0f}%)")
            elif ti.is_trusted:
                ti_score = 0.1  # trusted source reduces risk
                reasoning.append(f"Trusted source: {ti.source}")
            else:
                ti_score = 0.5
                reasoning.append(f"Threat intel: {ti.tag} (unknown)")
        else:
            reasoning.append("No threat intelligence available")
        components["threat_intel"] = ti_score * 100 * self.weights["threat_intel"]
        
        # 5. Repetition/persistence (15%)
        rep_score = self._compute_repetition_score(context)
        components["repetition"] = rep_score * 100 * self.weights["repetition"]
        if context.event_count > 1:
            reasoning.append(
                f"Repeated activity: {context.event_count} events, "
                f"{context.related_alerts} related alerts"
            )
        
        # 6. Asset importance (10%)
        asset_score = self._compute_asset_score(context)
        components["asset_importance"] = asset_score * 100 * self.weights["asset_importance"]
        if context.source_asset or context.target_asset:
            assets = []
            if context.source_asset:
                assets.append(f"src:{context.source_asset.importance}")
            if context.target_asset:
                assets.append(f"dst:{context.target_asset.importance}")
            reasoning.append(f"Asset importance: {', '.join(assets)}")
        
        # Compute total score
        total_score = sum(components.values())
        risk_score = max(0.0, min(100.0, total_score))
        risk_tier = RiskTier.from_score(risk_score)
        
        # Determine recommended action based on tier
        recommended_action = self._get_recommended_action(risk_tier, context)
        
        # Determine if human review required
        requires_review = risk_tier in (RiskTier.HIGH, RiskTier.CRITICAL) \
            or context.calibrated_confidence is not None and context.calibrated_confidence < 70
        
        # Determine severity
        severity = SeverityLevel.from_string(
            getattr(context, 'severity', context.predicted_class)
        )
        
        return RiskScoreResult(
            risk_score=risk_score,
            risk_tier=risk_tier,
            components={k: round(v, 2) for k, v in components.items()},
            reasoning=reasoning,
            confidence=confidence,
            severity=severity,
            recommended_action=recommended_action,
            requires_human_review=requires_review,
        )
    
    def _compute_repetition_score(self, context: AlertContext) -> float:
        """Compute repetition/persistence score (0-1)."""
        # Base score from event count (logarithmic)
        event_score = min(1.0, np.log1p(context.event_count) / np.log(101))
        
        # Related alerts bonus
        related_score = min(1.0, context.related_alerts / 10.0)
        
        # Time persistence bonus
        persistence_score = 0.0
        if context.first_seen and context.last_seen:
            duration = (context.last_seen - context.first_seen).total_seconds()
            # Full score after 1 hour of persistent activity
            persistence_score = min(1.0, duration / 3600)
        
        # Weighted combination
        return 0.5 * event_score + 0.3 * related_score + 0.2 * persistence_score
    
    def _compute_asset_score(self, context: AlertContext) -> float:
        """Compute asset importance score (0-1)."""
        scores = []
        
        if context.source_asset:
            scores.append(context.source_asset.to_weight())
        if context.target_asset:
            # Target asset is more important for risk
            scores.append(context.target_asset.to_weight() * 1.2)
        
        if not scores:
            return 0.5  # neutral
        
        # Use max (most important asset drives risk)
        return min(1.0, max(scores) / 1.25)
    
    def _get_recommended_action(self, tier: RiskTier, context: AlertContext) -> str:
        """Get recommended action based on risk tier."""
        actions = {
            RiskTier.CRITICAL: "Immediate containment: isolate source, block IP, escalate to IR team",
            RiskTier.HIGH: "Automated containment: block IP, rate limit, notify SOC analyst",
            RiskTier.MEDIUM: "Enhanced monitoring: increase logging, alert analyst, rate limit",
            RiskTier.GUARDED: "Log and monitor: increase logging, add to watchlist",
            RiskTier.LOW: "Log only: record for trend analysis",
        }
        base = actions.get(tier, "Log and monitor")
        
        # Add context-specific recommendations
        if context.threat_intel and context.threat_intel.is_trusted:
            base += " (Trusted source - verify before action)"
        
        return base


# Severity mapping for common attack types
ATTACK_SEVERITY_MAP = {
    "BENIGN": SeverityLevel.LOW,
    "DoS": SeverityLevel.HIGH,
    "DDoS": SeverityLevel.CRITICAL,
    "Port Scan": SeverityLevel.MEDIUM,
    "Bot": SeverityLevel.HIGH,
    "Brute Force": SeverityLevel.HIGH,
    "Web Attack - Brute Force": SeverityLevel.HIGH,
    "XSS": SeverityLevel.MEDIUM,
    "SQL Injection": SeverityLevel.HIGH,
    "Infiltration": SeverityLevel.CRITICAL,
    "Heartbleed": SeverityLevel.HIGH,
    "UNKNOWN": SeverityLevel.MEDIUM,
}


def get_attack_severity(attack_type: str) -> SeverityLevel:
    """Get severity level for an attack type."""
    return ATTACK_SEVERITY_MAP.get(attack_type, SeverityLevel.MEDIUM)


def compute_risk_score_for_alert(
    alert: Dict[str, Any],
    calibrator: Optional[ConfidenceCalibrator] = None,
    threat_intel: Optional[ThreatIntelContext] = None,
    asset_db: Optional[Dict[str, AssetContext]] = None,
    recent_alerts: Optional[List[Dict]] = None,
) -> RiskScoreResult:
    """
    High-level function to compute risk score for an alert from the SOC pipeline.
    
    Args:
        alert: Alert dict from detection pipeline
        calibrator: Optional confidence calibrator
        threat_intel: Threat intelligence for source/dest IPs
        asset_db: Asset database for IP -> asset mapping
        recent_alerts: Recent alerts for repetition detection
        
    Returns:
        RiskScoreResult with score and reasoning
    """
    scorer = RiskScorer()
    
    # Get calibrated confidence if calibrator available
    raw_confidence = alert.get("confidence", 0.0)
    calibrated_confidence = None
    if calibrator and "features" in alert:
        # Would need to extract features and run calibrator
        pass
    
    # Build context
    context = AlertContext(
        predicted_class=alert.get("attack_type", "UNKNOWN"),
        raw_confidence=raw_confidence,
        calibrated_confidence=calibrated_confidence,
        feature_coverage_ratio=alert.get("feature_coverage", 1.0),
        missing_features=alert.get("missing_features", []),
        threat_intel=threat_intel,
        source_ip=alert.get("source_ip", ""),
        dest_ip=alert.get("destination_ip", ""),
        source_port=alert.get("source_port", 0),
        dest_port=alert.get("destination_port", 0),
        protocol=alert.get("protocol", ""),
        model_version=alert.get("model_version", ""),
        processing_time_ms=alert.get("processing_time_ms", 0.0),
    )
    
    # Add severity from attack type
    context.predicted_class = alert.get("attack_type", "UNKNOWN")
    
    # Add threat intel if provided
    if threat_intel:
        context.threat_intel = threat_intel
    
    # Add asset context from database
    if asset_db:
        context.source_asset = asset_db.get(context.source_ip)
        context.target_asset = asset_db.get(context.dest_ip)
    
    # Compute repetition from recent alerts
    if recent_alerts:
        src_ip = context.source_ip
        same_src = [a for a in recent_alerts if a.get("source_ip") == src_ip]
        context.event_count = len(same_src) + 1
        context.related_alerts = len(same_src)
        if same_src:
            timestamps = [a.get("timestamp") for a in same_src if a.get("timestamp")]
            if timestamps:
                context.first_seen = min(timestamps)
                context.last_seen = max(timestamps)
    
    return scorer.compute_risk_score(context)


# Example usage:
#
# scorer = RiskScorer()
# context = AlertContext(
#     predicted_class="DoS",
#     raw_confidence=95.0,
#     calibrated_confidence=92.0,
#     feature_coverage_ratio=0.95,
#     threat_intel=ThreatIntelContext(tag="Known Malicious", source="internal", confidence=95),
#     target_asset=AssetContext("server1", "database", "critical"),
#     event_count=5,
#     related_alerts=3,
# )
# result = scorer.compute_risk_score(context)
# print(f"Risk: {result.risk_score:.1f} ({result.risk_tier.value})")
# print(f"Action: {result.recommended_action}")