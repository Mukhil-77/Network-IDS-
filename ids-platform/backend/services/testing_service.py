"""
Attack simulation service.

Generates synthetic attack alerts and injects them into the normal
detection pipeline - the same path a real detection takes:
DB record (FlowHistory + Alert) -> WebSocket broadcast -> response rules
evaluation (via AlertService.on_alert_persisted, when wired by main.py).

Simulated attack types (matching the frontend's attack-simulation page):
port_scan, syn_flood, udp_flood, icmp_flood, ssh_bruteforce, dns_attack,
custom. Each type carries realistic feature values so downstream consumers
(statistics, charts, response rules) see data shaped like real detections.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.database.connection import session_scope
from backend.database.models import Alert as AlertRow
from backend.database.models import FlowHistory
from backend.detection.alert import Alert as PydanticAlert
from backend.services.alert_service import alert_service
from backend.utils.logger import get_logger

logger = get_logger(__name__)

SUPPORTED_ATTACK_TYPES = {
    "port_scan": {
        "label": "PortScan",
        "severity": "medium",
        "packet_count": 480,
        "bytes": 120_000,
        "source_port": 49152,
        "destination_port": 445,
        "description": "Rapid TCP SYN probes across many ports",
    },
    "syn_flood": {
        "label": "DoS Hulk",
        "severity": "high",
        "packet_count": 12_000,
        "bytes": 960_000,
        "source_port": 50110,
        "destination_port": 80,
        "description": "High-volume TCP SYN flood against a web server",
    },
    "udp_flood": {
        "label": "DoS Slowloris",
        "severity": "high",
        "packet_count": 9_500,
        "bytes": 2_100_000,
        "source_port": 53210,
        "destination_port": 53,
        "description": "UDP datagram flood against DNS infrastructure",
    },
    "icmp_flood": {
        "label": "DDoS",
        "severity": "critical",
        "packet_count": 20_000,
        "bytes": 3_400_000,
        "source_port": 0,
        "destination_port": 0,
        "description": "Large ICMP echo-request flood",
    },
    "ssh_bruteforce": {
        "label": "SSH-Bruteforce",
        "severity": "high",
        "packet_count": 3_200,
        "bytes": 410_000,
        "source_port": 39210,
        "destination_port": 22,
        "description": "Repeated SSH authentication attempts from one source",
    },
    "dns_attack": {
        "label": "DNS",
        "severity": "medium",
        "packet_count": 2_600,
        "bytes": 880_000,
        "source_port": 51234,
        "destination_port": 53,
        "description": "Suspicious DNS query volume / tunneling pattern",
    },
    "custom": {
        "label": "Custom",
        "severity": "medium",
        "packet_count": 500,
        "bytes": 150_000,
        "source_port": 12345,
        "destination_port": 80,
        "description": "User-defined test event",
    },
}


class TestingService:
    """In-memory history of simulated attacks plus the injection logic."""

    def __init__(self, broadcaster=None) -> None:
        self._history: List[Dict[str, Any]] = []
        # Injectable so tests can substitute a fake; defaults to the real one.
        self._broadcaster = broadcaster if broadcaster is not None else alert_service.broadcaster

    # ------------------------------------------------------------------
    # Simulation entry point
    # ------------------------------------------------------------------

    def simulate_attack(
        self,
        *,
        attack_type: str = "port_scan",
        confidence: float = 0.99,
        source_ip: str = "192.168.1.100",
        destination_ip: str = "10.0.0.5",
        protocol: str = "TCP",
        severity: Optional[str] = None,
        operator: str = "analyst",
    ) -> Dict[str, Any]:
        """
        Create a synthetic FlowHistory + Alert pair, commit, broadcast over
        WebSocket, run response rules (if wired), and record simulation
        history. Returns the generated alert summary.
        """
        profile = SUPPORTED_ATTACK_TYPES.get(attack_type, SUPPORTED_ATTACK_TYPES["custom"])
        if severity is None:
            severity = profile["severity"]

        now = datetime.now(timezone.utc)
        flow_id = str(uuid.uuid4())
        alert_id = str(uuid.uuid4())

        with session_scope() as db:
            flow_row = FlowHistory(
                id=flow_id,
                protocol=protocol,
                source_ip=source_ip,
                destination_ip=destination_ip,
                source_port=profile["source_port"],
                destination_port=profile["destination_port"],
                start_time=now,
                end_time=now,
                packet_count=profile["packet_count"],
                byte_count=profile["bytes"],
            )
            db.add(flow_row)

            alert_row = AlertRow(
                id=alert_id,
                timestamp=now,
                attack_type=profile["label"],
                confidence=confidence,
                severity=severity,
                source_ip=source_ip,
                destination_ip=destination_ip,
                protocol=protocol,
                flow_id=flow_id,
                packet_count=profile["packet_count"],
                bytes=profile["bytes"],
                status="new",
                model_version="simulated",
            )
            db.add(alert_row)
            db.commit()

        alert_obj = PydanticAlert(
            id=alert_id,
            timestamp=now.isoformat(),
            attack=profile["label"],
            severity=severity,
            confidence=confidence,
            source_ip=source_ip,
            destination_ip=destination_ip,
            protocol=protocol,
            flow_id=flow_id,
            source_port=profile["source_port"],
            destination_port=profile["destination_port"],
            model_version="simulated",
        )
        self._broadcaster.publish_alert_threadsafe(alert_obj.model_dump())

        # Same snapshot shape AlertService passes to its on_alert_persisted
        # subscriber (response engine + threat-intel tagging in main.py).
        snapshot = {
            "id": alert_id,
            "severity": severity,
            "attack_type": profile["label"],
            "source_ip": source_ip,
            "destination_ip": destination_ip,
            "flow_id": flow_id,
        }
        if alert_service.on_alert_persisted is not None:
            try:
                alert_service.on_alert_persisted(snapshot)
            except Exception:  # noqa: BLE001 - simulation must never crash on a subscriber bug
                logger.exception("on_alert_persisted callback raised for simulated alert %s", alert_id)

        record = {
            "timestamp": now.isoformat(),
            "attack_type": profile["label"],
            "severity": severity,
            "source_ip": source_ip,
            "description": profile["description"],
            "status": "success",
            "operator": operator,
        }
        self._history.insert(0, record)

        logger.info("Simulated attack '%s' (severity=%s) -> alert %s", profile["label"], severity, alert_id)
        return {"message": "Attack simulated successfully", "alert_id": alert_id, "attack_type": profile["label"]}

    def get_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self._history[:limit]


# Process-wide instance - api/routes/testing.py and tests import this.
testing_service = TestingService()
