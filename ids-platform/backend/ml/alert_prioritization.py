"""
Alert Prioritization and Incident Grouping

Implements P1-P4 alert prioritization based on:
- Risk score
- Severity
- Confidence
- Attack type
- Repeated activity
- Source reputation/history
- Number of related alerts
- Persistence over time

Also implements incident grouping to reduce alert fatigue.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Optional
from collections import defaultdict

import pandas as pd

from backend.ml.risk_scoring import PredictionResult, RiskLevel
from backend.ml.severity import get_severity, SeverityLevel
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class AlertPriority(Enum):
    P1_CRITICAL = "P1_CRITICAL"
    P2_HIGH = "P2_HIGH"
    P3_MEDIUM = "P3_MEDIUM"
    P4_LOW = "P4_LOW"


@dataclass
class Alert:
    """Enhanced alert with prioritization and grouping."""
    alert_id: str
    timestamp: datetime
    attack_type: str
    confidence: float
    severity: str
    risk_score: int
    risk_level: str
    source_ip: str
    destination_ip: str
    source_port: int
    destination_port: int
    protocol: str
    flow_id: str
    packet_count: int
    bytes: int
    status: str = "new"
    model_version: str = ""
    processing_time_ms: float = 0.0
    threat_tag: str = "Unknown"
    
    # Prioritization fields
    priority: AlertPriority = AlertPriority.P4_LOW
    priority_score: float = 0.0
    is_grouped: bool = False
    group_id: Optional[str] = None
    group_size: int = 1
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    
    def to_dict(self) -> dict:
        return {
            "alert_id": self.alert_id,
            "timestamp": self.timestamp.isoformat(),
            "attack_type": self.attack_type,
            "confidence": self.confidence,
            "severity": self.severity,
            "risk_score": self.risk_score,
            "risk_level": self.risk_level,
            "source_ip": self.source_ip,
            "destination_ip": self.destination_ip,
            "source_port": self.source_port,
            "destination_port": self.destination_port,
            "protocol": self.protocol,
            "flow_id": self.flow_id,
            "packet_count": self.packet_count,
            "bytes": self.bytes,
            "status": self.status,
            "model_version": self.model_version,
            "processing_time_ms": self.processing_time_ms,
            "threat_tag": self.threat_tag,
            "priority": self.priority.value,
            "priority_score": self.priority_score,
            "is_grouped": self.is_grouped,
            "group_id": self.group_id,
            "group_size": self.group_size,
            "first_seen": self.first_seen.isoformat() if self.first_seen else None,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
        }


@dataclass
class Incident:
    """Aggregated incident from grouped alerts."""
    incident_id: str
    group_id: str
    attack_type: str
    severity: str
    risk_level: str
    source_ip: str
    destination_ip: str
    alert_count: int
    first_seen: datetime
    last_seen: datetime
    total_bytes: int
    total_packets: int
    aggregated_risk_score: float
    severity_level: str
    status: str = "open"
    related_alerts: list[str] = field(default_factory=list)
    recommended_actions: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "incident_id": self.incident_id,
            "group_id": self.group_id,
            "attack_type": self.attack_type,
            "severity": self.severity,
            "risk_level": self.risk_level,
            "source_ip": self.source_ip,
            "destination_ip": self.destination_ip,
            "alert_count": self.alert_count,
            "first_seen": self.first_seen.isoformat(),
            "last_seen": self.last_seen.isoformat(),
            "total_bytes": self.total_bytes,
            "total_packets": self.total_packets,
            "aggregated_risk_score": self.aggregated_risk_score,
            "severity_level": self.severity_level,
            "status": self.status,
            "related_alerts": self.related_alerts,
            "recommended_actions": self.recommended_actions,
        }


class AlertPrioritizer:
    """
    Prioritizes alerts based on multiple factors:
    - Risk score
    - Severity
    - Confidence
    - Attack type
    - Repeated activity
    - Source reputation/history
    - Number of related alerts
    - Persistence over time
    """
    
    # Priority weights
    PRIORITY_WEIGHTS = {
        "risk_score": 0.30,
        "severity": 0.20,
        "confidence": 0.15,
        "attack_type_weight": 0.10,
        "frequency": 0.10,
        "source_reputation": 0.10,
        "persistence": 0.05,
    }
    
    # Attack type priority weights
    ATTACK_TYPE_WEIGHTS = {
        "DDoS": 1.0,
        "DoS": 0.9,
        "SQL Injection": 0.95,
        "Infiltration": 0.95,
        "Backdoor": 0.95,
        "Shellcode": 0.95,
        "Worms": 0.95,
        "Bot": 0.85,
        "Web Attack - Brute Force": 0.8,
        "Brute Force": 0.75,
        "DoS": 0.9,
        "XSS": 0.7,
        "SQL Injection": 0.95,
        "Port Scan": 0.5,
        "Port Scan": 0.5,
        "Brute Force": 0.75,
        "Fuzzer": 0.4,
        "Reconnaissance": 0.2,
        "Analysis": 0.2,
        "Heartbleed": 0.6,
        "Infiltration": 0.95,
        "Bot": 0.85,
        "Heartbleed": 0.6,
        "Exploit": 0.9,
        "Fuzzer": 0.4,
        "Reconnaissance": 0.2,
        "Analysis": 0.2,
        "Backdoor": 0.95,
        "Shellcode": 0.95,
        "Worms": 0.95,
        "UNKNOWN": 0.8,
        "Known Malicious": 0.95,
        "Suspicious": 0.7,
        "Trusted": 0.1,
        "Legitimate": 0.1,
    }
    
    def __init__(self):
        self.alert_history: list = []  # In-memory history (replace with DB in production)
    
    def calculate_priority_score(self, alert: Alert, context: dict = None) -> float:
        """
        Calculate priority score (0-100) for an alert.
        
        Factors:
        - risk_score (0-100): 30%
        - severity: 20%
        - confidence: 15%
        - attack_type_weight: 10%
        - frequency: 10%
        - source_reputation: 10%
        - persistence: 5%
        """
        score = 0.0
        
        # 1. Risk score (0-100)
        risk_score_normalized = alert.risk_score / 100.0
        score += self.PRIORITY_WEIGHTS["risk_score"] * risk_score_normalized
        
        # 2. Severity
        severity_score = self._severity_to_score(alert.severity)
        score += self.PRIORITY_WEIGHTS["severity"] * severity_score
        
        # 3. Confidence (0-100)
        confidence_normalized = alert.confidence / 100.0
        score += self.PRIORITY_WEIGHTS["confidence"] * confidence_normalized
        
        # 4. Attack type weight
        attack_weight = self.ATTACK_TYPE_WEIGHTS.get(alert.attack_type, 0.5)
        score += self.PRIORITY_WEIGHTS["attack_type_weight"] * attack_weight
        
        # 4. Frequency (repeated alerts from same source)
        if hasattr(self, 'alert_history'):
            frequency = self._compute_frequency(alert.source_ip)
            score += self.PRIORITY_WEIGHTS["frequency"] * frequency
        
        # 5. Source reputation (placeholder)
        reputation_score = 0.5  # neutral
        score += self.PRIORITY_WEIGHTS["source_reputation"] * reputation_score
        
        # 6. Persistence (placeholder)
        persistence_score = 0.0
        score += self.PRIORITY_WEIGHTS["persistence"] * persistence_score
        
        return min(100.0, max(0.0, score * 100))
    
    def _severity_to_score(self, severity: str) -> float:
        """Convert severity to normalized score (0-1)."""
        return {
            "CRITICAL": 1.0,
            "HIGH": 0.75,
            "MEDIUM": 0.5,
            "LOW": 0.25,
        }.get(severity, 0.5)
    
    def _compute_frequency(self, source_ip: str) -> float:
        """Compute frequency score based on recent alerts from same source."""
        # Placeholder - would query database for recent alerts
        return 0.0
    
    def prioritize_alert(self, alert: Alert, context: dict = None) -> Alert:
        """Calculate and assign priority to an alert."""
        priority_score = self.calculate_priority_score(alert)
        alert.priority_score = priority_score
        
        # Assign priority level
        if priority_score >= 80:
            alert.priority = AlertPriority.P1_CRITICAL
        elif priority_score >= 60:
            alert.priority = AlertPriority.P2_HIGH
        elif priority_score >= 40:
            alert.priority = AlertPriority.P3_MEDIUM
        else:
            alert.priority = AlertPriority.P4_LOW
        
        return alert
    
    def prioritize_alerts(self, alerts: list[Alert], context: dict = None) -> list[Alert]:
        """Prioritize a list of alerts and sort by priority."""
        for alert in alerts:
            self.prioritize_alert(alert)
        
        # Sort by priority score (highest first)
        alerts.sort(key=lambda a: a.priority_score, reverse=True)
        return alerts


class AlertGrouper:
    """
    Groups related alerts into incidents to reduce alert fatigue.
    
    Grouping criteria:
    - Same source IP
    - Same attack type
    - Time proximity (within time window)
    - Same destination
    """
    
    def __init__(
        self,
        time_window_minutes: int = 60,
        min_group_size: int = 2,
        max_group_size: int = 100,
    ):
        self.time_window = timedelta(minutes=time_window_minutes)
        self.min_group_size = min_group_size
        self.max_group_size = max_group_size
        self.groups: dict[str, list[Alert]] = defaultdict(list)
    
    def group_alerts(self, alerts: list[Alert]) -> dict[str, list[Alert]]:
        """
        Group alerts by source IP, attack type, and time proximity.
        
        Returns dict of group_id -> list of alerts.
        """
        # Sort alerts by timestamp
        alerts_sorted = sorted(alerts, key=lambda a: a.timestamp)
        
        groups = defaultdict(list)
        group_counter = 0
        
        for alert in alerts_sorted:
            # Try to find existing group
            group_key = self._find_group(alert, groups)
            
            if group_key is None:
                # Create new group
                group_key = f"group_{len(groups) + 1}_{alert.timestamp.strftime('%Y%m%d_%H%M%S')}"
            
            groups[group_key].append(alert)
        
        # Filter groups by minimum size
        filtered_groups = {
            k: v for k, v in groups.items() 
            if len(v) >= self.min_group_size
        }
        
        # Update alert group info
        for group_id, group_alerts in filtered_groups.items():
            if len(group_alerts) > self.max_group_size:
                group_alerts = group_alerts[:self.max_group_size]
            
            first_seen = min(a.timestamp for a in group_alerts)
            last_seen = max(a.timestamp for a in group_alerts)
            
            for alert in group_alerts:
                alert.is_grouped = True
                alert.group_id = group_id
                alert.group_size = len(group_alerts)
                alert.first_seen = min(a.timestamp for a in group_alerts)
                alert.last_seen = max(a.timestamp for a in group_alerts)
        
        return filtered_groups
    
    def _find_group(self, alert: Alert, groups: dict) -> Optional[str]:
        """Find existing group for alert based on grouping criteria."""
        for group_id, group_alerts in groups.items():
            if len(group_alerts) >= self.max_group_size:
                continue
            
            # Check if same source IP
            if group_alerts[0].source_ip != alert.source_ip:
                continue
            
            # Check if same attack type
            if group_alerts[0].attack_type != alert.attack_type:
                continue
            
            # Check time proximity
            last_alert_time = max(a.timestamp for a in group_alerts)
            if alert.timestamp - last_alert_time > self.time_window:
                continue
            
            return group_id
        
        return None


class IncidentManager:
    """
    Manages incident creation, tracking, and resolution from grouped alerts.
    """
    
    def __init__(self):
        self.incidents: dict[str, Incident] = {}
    
    def create_incidents_from_groups(self, groups: dict[str, list[Alert]]) -> list[Incident]:
        """Create incidents from grouped alerts."""
        incidents = []
        
        for group_id, alert_list in groups.items():
            if not alert_list:
                continue
            
            first_alert = alert_list[0]
            last_alert = alert_list[-1]
            
            # Calculate aggregated metrics
            total_bytes = sum(a.bytes for a in alert_list)
            total_packets = sum(a.packet_count for a in alert_list)
            
            # Aggregate risk score (max)
            max_risk = max(a.risk_score for a in alert_list)
            avg_risk = sum(a.risk_score for a in alert_list) / len(alert_list)
            
            # Determine severity
            severity = self._determine_severity(alert_list)
            risk_level = self._determine_risk_level(alert_list)
            
            # Generate recommended actions
            actions = self._generate_recommended_actions(alert_list)
            
            incident = Incident(
                incident_id=f"INC-{datetime.now().strftime('%Y%m%d%H%M%S')}-{len(self.incidents) + 1}",
                group_id=alert_list[0].group_id,
                attack_type=alert_list[0].attack_type,
                severity=severity,
                risk_level=risk_level,
                source_ip=alert_list[0].source_ip,
                destination_ip=alert_list[0].destination_ip,
                alert_count=len(alert_list),
                first_seen=min(a.timestamp for a in alert_list),
                last_seen=max(a.timestamp for a in alert_list),
                total_bytes=sum(a.bytes for a in alert_list),
                total_packets=sum(a.packet_count for a in alert_list),
                aggregated_risk_score=sum(a.risk_score for a in alert_list) / len(alert_list),
                severity_level=severity,
                status="open",
                related_alerts=[a.alert_id for a in alert_list],
                recommended_actions=actions,
            )
            
            self.incidents[incident.incident_id] = incident
            incidents.append(incident)
        
        return list(self.incidents.values())
    
    def _determine_severity(self, alerts: list[Alert]) -> str:
        """Determine overall severity from alerts."""
        severity_scores = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}
        max_severity = max(severity_scores.get(a.severity, 1) for a in alerts)
        for sev, score in severity_scores.items():
            if score == max_severity:
                return sev
        return "MEDIUM"
    
    def _determine_risk_level(self, alerts: list[Alert]) -> str:
        """Determine overall risk level from alerts."""
        avg_risk = sum(a.risk_score for a in alerts) / len(alerts)
        if avg_risk >= 80:
            return "CRITICAL"
        elif avg_risk >= 60:
            return "HIGH"
        elif avg_risk >= 40:
            return "MEDIUM"
        elif risk_score >= 20:
            return "GUARDED"
        else:
            return "LOW"
    
    def _generate_recommended_actions(self, alerts: list[Alert]) -> list[str]:
        """Generate recommended response actions based on alert types."""
        actions = set()
        
        for alert in alerts:
            if alert.severity == "CRITICAL":
                actions.add("Immediate investigation required")
                actions.add("Consider immediate containment/isolation")
            elif alert.severity == "HIGH":
                actions.add("Priority investigation within 1 hour")
                actions.add("Monitor source IP closely")
            elif alert.severity == "MEDIUM":
                actions.add("Schedule investigation within 4 hours")
            else:
                actions.add("Log for trend analysis")
            
            # Attack-type specific actions
            if "DDoS" in alert.attack_type or "DoS" in alert.attack_type:
                actions.add("Activate DDoS mitigation")
            elif "SQL Injection" in alert.attack_type:
                actions.add("Review WAF rules and database logs")
            elif "SQL Injection" in alert.attack_type:
                actions.add("Check for data exfiltration")
            elif "Port Scan" in alert.attack_type:
                actions.add("Monitor for follow-up exploitation attempts")
        
        return list(actions)


def create_alert_from_prediction(
    prediction: 'PredictionResult',
    flow_id: str,
    source_ip: str,
    destination_ip: str,
    source_port: int,
    destination_port: int,
    protocol: str,
    packet_count: int,
    bytes: int,
    model_version: str = "v4",
) -> Alert:
    """Create an Alert from a PredictionResult."""
    from backend.ml.risk_scoring import PredictionResult
    
    alert = Alert(
        alert_id=f"ALERT-{datetime.now().strftime('%Y%m%d%H%M%S')}-{hash(flow_id) % 10000:04d}",
        timestamp=datetime.now(timezone.utc),
        attack_type=prediction.predicted_class,
        confidence=prediction.model_confidence,
        severity=prediction.severity,
        risk_score=prediction.risk_score,
        risk_level=prediction.risk_level.value if hasattr(prediction.risk_level, 'value') else str(prediction.risk_level),
        source_ip=source_ip,
        destination_ip=destination_ip,
        source_port=source_port,
        destination_port=destination_port,
        protocol=protocol,
        flow_id=flow_id,
        packet_count=packet_count,
        bytes=bytes,
        model_version="v4",
        threat_tag="Unknown",
    )
    return alert


if __name__ == "__main__":
    print("Alert prioritization module loaded successfully")