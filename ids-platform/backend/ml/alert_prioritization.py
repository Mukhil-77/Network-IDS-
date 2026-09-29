"""
Alert prioritization and incident grouping for SOC dashboard.

Implements risk-based alert prioritization (P1-P4), incident grouping
for repetitive alerts, and SOC dashboard integration.

Research contribution: Risk-based SOC alert prioritization and controlled response.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from collections import defaultdict

from backend.ml.risk_scoring import (
    RiskScorer, 
    RiskScoreResult, 
    RiskTier, 
    SeverityLevel,
    AlertContext,
    ThreatIntelContext,
    AssetContext,
)
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class PriorityLevel(Enum):
    """Alert priority levels for SOC queue."""
    P1 = "P1"      # CRITICAL - Immediate action required
    P2 = "P2"      # HIGH - Action within 15 minutes
    P3 = "P3"      # MEDIUM - Action within 1 hour
    P4 = "P4"      # LOW - Review within shift
    
    @classmethod
    def from_risk_tier(cls, tier: 'RiskTier') -> 'PriorityLevel':
        mapping = {
            'CRITICAL': cls.P1,
            'HIGH': cls.P2,
            'MEDIUM': cls.P3,
            'GUARDED': cls.P4,
            'LOW': cls.P4,
        }
        return mapping.get(tier.value, cls.P4)
    
    def sla_minutes(self) -> int:
        """SLA in minutes for this priority."""
        return {
            PriorityLevel.P1: 15,
            PriorityLevel.P2: 60,
            PriorityLevel.P3: 240,  # 4 hours
            PriorityLevel.P4: 480,  # 8 hours
        }[self]
    
    def color(self) -> str:
        """CSS color for UI."""
        return {
            PriorityLevel.P1: "text-red-500",
            PriorityLevel.P2: "text-orange-500",
            PriorityLevel.P3: "text-yellow-500",
            PriorityLevel.P4: "text-blue-500",
        }[self]


@dataclass
class PrioritizedAlert:
    """Alert with priority and risk scoring."""
    alert_id: str
    timestamp: datetime
    attack_type: str
    source_ip: str
    dest_ip: str
    severity: str
    confidence: float
    risk_score: float
    risk_tier: str
    priority: PriorityLevel
    risk_components: Dict[str, float]
    reasoning: List[str]
    recommended_action: str
    requires_review: bool
    # Grouping info
    incident_id: Optional[str] = None
    is_group_representative: bool = False
    group_size: int = 1


@dataclass
class Incident:
    """Grouped incident from repetitive alerts."""
    incident_id: str
    created_at: datetime
    updated_at: datetime
    attack_type: str
    source_ip: str
    dest_ips: Set[str]
    source_ports: Set[int]
    dest_ports: Set[int]
    protocols: Set[str]
    first_seen: datetime
    last_seen: datetime
    event_count: int
    unique_alerts: int
    max_risk_score: float
    current_risk_tier: str
    priority: PriorityLevel
    status: str = "open"  # open, investigating, contained, closed
    assigned_analyst: Optional[str] = None
    risk_score_trend: List[Tuple[datetime, float]] = field(default_factory=list)
    affected_assets: List[str] = field(default_factory=list)
    threat_intel_tags: List[str] = field(default_factory=list)
    response_actions: List[Dict] = field(default_factory=list)
    containment_verified: bool = False
    
    def add_alert(self, alert: PrioritizedAlert):
        """Add an alert to this incident."""
        self.event_count += 1
        self.unique_alerts += 1
        self.last_seen = max(self.last_seen, alert.timestamp)
        self.max_risk_score = max(self.max_risk_score, alert.risk_score)
        self.risk_score_trend.append((alert.timestamp, alert.risk_score))
        if alert.dest_ip not in self.dest_ips:
            self.dest_ips.add(alert.dest_ip)
        if alert.source_ip not in self.dest_ips:  # also track source
            pass
        if alert.dest_port:
            self.dest_ports.add(alert.dest_port)
        if alert.protocol:
            self.protocols.add(alert.protocol)
        if alert.risk_tier in ("HIGH", "CRITICAL"):
            self.priority = PriorityLevel.from_risk_tier(alert.risk_tier)
    
    def to_summary(self) -> Dict[str, Any]:
        """Generate incident summary for SOC dashboard."""
        return {
            "incident_id": self.incident_id,
            "attack_type": self.attack_type,
            "source_ip": self.source_ip,
            "dest_ips": list(self.dest_ips)[:10],  # limit display
            "event_count": self.event_count,
            "unique_alerts": self.unique_alerts,
            "first_seen": self.first_seen.isoformat(),
            "last_seen": self.last_seen.isoformat(),
            "duration_minutes": int((self.last_seen - self.first_seen).total_seconds() / 60),
            "max_risk_score": round(self.max_risk_score, 1),
            "current_risk_tier": self.current_risk_tier,
            "priority": self.priority.value,
            "status": self.status,
            "affected_assets": self.affected_assets,
            "threat_intel_tags": self.threat_intel_tags,
            "response_actions": len(self.response_actions),
            "containment_verified": self.containment_verified,
        }


class AlertPrioritizer:
    """
    Prioritizes alerts and groups them into incidents.
    
    Uses risk scoring to assign P1-P4 priorities and groups
    repetitive alerts into incidents to reduce alert fatigue.
    """
    
    def __init__(
        self,
        risk_scorer: Any = None,
        grouping_window_minutes: int = 60,
        similarity_threshold: float = 0.8,
        max_incident_duration_hours: int = 24,
    ):
        self.risk_scorer = risk_scorer
        self.grouping_window = timedelta(minutes=grouping_window_minutes)
        self.similarity_threshold = similarity_threshold
        self.max_incident_duration = timedelta(hours=max_incident_duration_hours)
        self.incidents: Dict[str, Incident] = {}
        self.alert_to_incident: Dict[str, str] = {}
    
    def prioritize_alert(self, context: AlertContext) -> PrioritizedAlert:
        """
        Prioritize a single alert using risk scoring.
        
        Args:
            context: Alert context with all scoring signals
            
        Returns:
            PrioritizedAlert with priority, risk score, and reasoning
        """
        if self.risk_scorer:
            risk_result = self.risk_scorer.compute_risk_score(context)
        else:
            # Fallback scoring
            risk_result = self._fallback_scoring(context)
        
        priority = PriorityLevel.from_risk_tier(risk_result.risk_tier)
        
        return PrioritizedAlert(
            alert_id=context.alert_id if hasattr(context, 'alert_id') else "",
            timestamp=datetime.now(),
            attack_type=context.predicted_class,
            source_ip=context.source_ip,
            dest_ip=context.dest_ip,
            severity=context.predicted_class,  # Use attack type as severity fallback
            confidence=context.calibrated_confidence or context.raw_confidence,
            risk_score=risk_result.risk_score,
            risk_tier=risk_result.risk_tier.value,
            priority=priority,
            risk_components=risk_result.components,
            reasoning=risk_result.reasoning,
            recommended_action=risk_result.recommended_action,
            requires_review=risk_result.requires_human_review,
        )
    
    def _fallback_scoring(self, context: AlertContext) -> 'RiskScoreResult':
        """Fallback risk scoring when risk_scorer not available."""
        from backend.ml.risk_scoring import RiskScoreResult, RiskTier, SeverityLevel
        
        # Simple scoring based on confidence and severity
        confidence = context.calibrated_confidence or context.raw_confidence
        severity = SeverityLevel.from_string(context.predicted_class)
        
        score = (confidence * 0.6) + (severity.to_weight() * 100 * 0.4)
        
        if score >= 80:
            tier = RiskTier.CRITICAL
        elif score >= 60:
            tier = RiskTier.HIGH
        elif score >= 40:
            tier = RiskTier.MEDIUM
        elif score >= 20:
            tier = RiskTier.GUARDED
        else:
            tier = RiskTier.LOW
        
        return RiskScoreResult(
            risk_score=score,
            risk_tier=tier,
            components={"confidence": confidence * 0.6, "severity": severity.to_weight() * 40},
            reasoning=[f"Fallback scoring: confidence={confidence:.1f}%"],
            confidence=confidence,
            severity=severity,
            recommended_action="Review alert",
            requires_human_review=tier in (RiskTier.HIGH, RiskTier.CRITICAL),
        )
    
    def group_alerts_into_incidents(
        self, 
        alerts: List[PrioritizedAlert],
        existing_incidents: Optional[Dict[str, Incident]] = None,
    ) -> Dict[str, Incident]:
        """
        Group prioritized alerts into incidents.
        
        Grouping criteria:
        - Same source IP
        - Same attack type
        - Within time window
        - Similar destination (subnet match)
        
        Args:
            alerts: List of prioritized alerts
            existing_incidents: Existing incidents to merge with
            
        Returns:
            Dict of incident_id -> Incident
        """
        if existing_incidents:
            self.incidents = existing_incidents
        
        # Sort alerts by timestamp
        alerts.sort(key=lambda a: a.timestamp)
        
        for alert in alerts:
            self._assign_to_incident(alert)
        
        # Clean up old incidents
        self._cleanup_old_incidents()
        
        return self.incidents
    
    def _assign_to_incident(self, alert: PrioritizedAlert):
        """Assign alert to existing incident or create new one."""
        # Find matching incident
        matching_incident = None
        best_similarity = 0.0
        
        for incident in self.incidents.values():
            # Skip closed incidents
            if incident.status == "closed":
                continue
            
            # Check time window
            if alert.timestamp - incident.last_seen > self.grouping_window:
                continue
            
            # Check max duration
            if alert.timestamp - incident.first_seen > self.max_incident_duration:
                continue
            
            # Compute similarity
            similarity = self._compute_similarity(alert, incident)
            
            if similarity > best_similarity and similarity >= self.similarity_threshold:
                best_similarity = similarity
                matching_incident = incident
        
        if matching_incident:
            # Add to existing incident
            matching_incident.add_alert(alert)
            alert.incident_id = matching_incident.incident_id
            alert.group_size = matching_incident.unique_alerts
            self.alert_to_incident[alert.alert_id] = matching_incident.incident_id
        else:
            # Create new incident
            incident_id = f"INC-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{len(self.incidents)+1:04d}"
            incident = Incident(
                incident_id=incident_id,
                created_at=alert.timestamp,
                updated_at=alert.timestamp,
                attack_type=alert.attack_type,
                source_ip=alert.source_ip,
                dest_ips={alert.dest_ip},
                source_ports={alert.dest_port} if alert.dest_port else set(),
                dest_ports={alert.dest_port} if alert.dest_port else set(),
                protocols={alert.protocol} if alert.protocol else set(),
                first_seen=alert.timestamp,
                last_seen=alert.timestamp,
                event_count=1,
                unique_alerts=1,
                max_risk_score=alert.risk_score,
                current_risk_tier=alert.risk_tier,
                priority=alert.priority,
            )
            self.incidents[incident_id] = incident
            alert.incident_id = incident_id
            alert.is_group_representative = True
            alert.group_size = 1
            self.alert_to_incident[alert.alert_id] = incident_id
    
    def _compute_similarity(self, alert: PrioritizedAlert, incident: Incident) -> float:
        """Compute similarity between alert and incident (0-1)."""
        score = 0.0
        weights = {
            "source_ip": 0.4,
            "attack_type": 0.3,
            "dest_subnet": 0.2,
            "protocol": 0.1,
        }
        
        # Source IP exact match
        if alert.source_ip == incident.source_ip:
            score += weights["source_ip"]
        
        # Attack type match
        if alert.attack_type == incident.attack_type:
            score += weights["attack_type"]
        
        # Destination subnet match (/24)
        alert_subnet = ".".join(alert.dest_ip.split(".")[:3])
        incident_subnets = set(".".join(ip.split(".")[:3]) for ip in incident.dest_ips)
        if alert_subnet in incident_subnets:
            score += weights["dest_subnet"]
        
        # Protocol match
        if alert.protocol and alert.protocol in incident.protocols:
            score += weights["protocol"]
        
        return score
    
    def _cleanup_old_incidents(self):
        """Remove or archive incidents older than max duration."""
        now = datetime.now()
        to_remove = []
        
        for inc_id, incident in self.incidents.items():
            if now - incident.last_seen > self.max_incident_duration:
                if incident.status == "open":
                    incident.status = "stale"
                # Keep stale incidents for history but don't match new alerts
                # Could move to archive instead of removing
                # to_remove.append(inc_id)
        
        for inc_id in to_remove:
            del self.incidents[inc_id]
    
    def get_soc_dashboard_data(self) -> Dict[str, Any]:
        """Get data for SOC dashboard."""
        open_incidents = [i for i in self.incidents.values() if i.status == "open"]
        critical = [i for i in open_incidents if i.priority == PriorityLevel.P1]
        high = [i for i in open_incidents if i.priority == PriorityLevel.P2]
        
        return {
            "total_incidents": len(open_incidents),
            "p1_critical": len(critical),
            "p2_high": len(high),
            "p3_medium": len([i for i in open_incidents if i.priority == PriorityLevel.P3]),
            "p4_low": len([i for i in open_incidents if i.priority == PriorityLevel.P4]),
            "top_incidents": sorted(
                open_incidents, 
                key=lambda i: i.max_risk_score, 
                reverse=True
            )[:10],
            "total_events_last_hour": sum(i.event_count for i in open_incidents),
            "unique_sources": len(set(i.source_ip for i in open_incidents)),
        }


# Convenience functions for SOC integration

def prioritize_alerts_batch(
    alerts: List[Dict[str, Any]],
    risk_scorer: Any = None,
    asset_db: Optional[Dict[str, Any]] = None,
    threat_intel_db: Optional[Dict[str, Any]] = None,
) -> List[PrioritizedAlert]:
    """
    Prioritize a batch of alerts from the SOC pipeline.
    
    Args:
        alerts: List of alert dicts from detection pipeline
        risk_scorer: RiskScorer instance
        asset_db: Asset database for IP -> asset mapping
        threat_intel_db: Threat intel database
        
    Returns:
        List of PrioritizedAlert sorted by priority (P1 first)
    """
    prioritizer = AlertPrioritizer(risk_scorer=risk_scorer)
    prioritized = []
    
    for alert in alerts:
        # Build context from alert
        context = AlertContext(
            predicted_class=alert.get("attack_type", "UNKNOWN"),
            raw_confidence=alert.get("confidence", 0.0),
            calibrated_confidence=alert.get("calibrated_confidence"),
            feature_coverage_ratio=alert.get("feature_coverage", 1.0),
            missing_features=alert.get("missing_features", []),
            source_ip=alert.get("source_ip", ""),
            dest_ip=alert.get("destination_ip", ""),
            source_port=alert.get("source_port", 0),
            dest_port=alert.get("destination_port", 0),
            protocol=alert.get("protocol", ""),
            model_version=alert.get("model_version", ""),
            processing_time_ms=alert.get("processing_time_ms", 0.0),
            alert_id=alert.get("id", ""),
        )
        
        # Add threat intel if available
        if threat_intel_db and context.source_ip in threat_intel_db:
            ti_data = threat_intel_db[context.source_ip]
            from backend.ml.risk_scoring import ThreatIntelContext
            context.threat_intel = ThreatIntelContext(
                tag=ti_data.get("tag", "Unknown"),
                source=ti_data.get("source", "unknown"),
                confidence=ti_data.get("confidence", 0.0),
                notes=ti_data.get("notes", ""),
            )
        
        # Add asset context
        if asset_db:
            if context.source_ip in asset_db:
                context.source_asset = asset_db[context.source_ip]
            if context.dest_ip in asset_db:
                context.target_asset = asset_db[context.dest_ip]
        
        # Prioritize
        prioritized = prioritizer.prioritize_alert(context)
        prioritized.append(prioritized)
    
    # Sort by priority (P1 first), then by risk score descending
    priority_order = {"P1": 0, "P2": 1, "P3": 2, "P4": 3}
    prioritized.sort(key=lambda a: (priority_order[a.priority.value], -a.risk_score))
    
    return prioritized


def create_incidents_from_alerts(
    prioritized_alerts: List[PrioritizedAlert],
    grouping_window_minutes: int = 60,
) -> Dict[str, Incident]:
    """
    Create incidents from prioritized alerts.
    
    Returns dict of incident_id -> Incident
    """
    prioritizer = AlertPrioritizer(grouping_window_minutes=grouping_window_minutes)
    return prioritizer.group_alerts_into_incidents(prioritized_alerts)


# Example usage:
#
# from backend.ml.alert_prioritization import (
#     prioritize_alerts_batch, create_incidents_from_alerts, Incident
# )
# from backend.ml.risk_scoring import RiskScorer
#
# # Prioritize alerts from SOC pipeline
# prioritized = prioritize_alerts_batch(
#     alerts=soc_alerts,
#     risk_scorer=RiskScorer(),
#     asset_db=asset_database,
#     threat_intel_db=threat_intel_db,
# )
#
# # Group into incidents
# incidents = create_incidents_from_alerts(prioritized)
#
# # Display on SOC dashboard
# for incident in incidents.values():
#     if incident.priority in (PriorityLevel.P1, PriorityLevel.P2):
#         print(f"[{incident.priority.value}] {incident.attack_type} from {incident.source_ip}")
#         print(f"  Events: {incident.event_count}, Risk: {incident.max_risk_score:.1f}")
#         print(f"  Action: {incident.recommended_action}")