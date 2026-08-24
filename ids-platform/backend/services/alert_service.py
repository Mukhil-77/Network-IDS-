"""
The receiving end of DetectionService's `on_alert_generated` callback
(Milestone 5's one additive extension point - see detection_service.py).

    DetectionService (worker thread)
        v  on_alert_generated(alert, flow, prediction)
    AlertService.handle_detection()
        v
    1. write FlowHistory row       )
    2. write Alert row (FK'd to 1) ) one DB session, one commit
    3. upsert AttackStatistics     )
        v
    4. broadcast over WebSocket (via broadcaster - non-blocking, see broadcaster.py)

Runs on the same detection worker thread DetectionService already uses
(Milestone 5 put that off the packet-capture thread) - so this synchronous
DB write never blocks packet capture, without needing yet another thread
pool. See database/connection.py's docstring for why the DB layer is sync
in the first place.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, Optional

from backend.database.connection import session_scope
from backend.database.models import Alert as AlertRow
from backend.database.models import FlowHistory
from backend.database.repositories.alerts import AlertRepository
from backend.database.repositories.flows import FlowRepository
from backend.database.repositories.statistics import AttackStatisticsRepository
from backend.detection.alert import Alert
from backend.ml.schemas import PredictionResponse
from backend.packet_capture.flow_manager import Flow
from backend.utils.logger import get_logger
from backend.websocket.broadcaster import AlertBroadcaster, broadcaster as default_broadcaster
from backend.threat_intelligence.reputation import reputation_registry as _reputation_registry

logger = get_logger(__name__)

# Milestone 8: fired after an alert is persisted+broadcast, with a plain
# dict snapshot (not the ORM row - which would be detached once the DB
# session closes): {id, severity, attack_type, source_ip, destination_ip, flow_id}.
OnAlertPersisted = Callable[[dict], None]


class AlertService:
    def __init__(
        self,
        broadcaster: AlertBroadcaster = default_broadcaster,
        on_alert_persisted: Optional[OnAlertPersisted] = None,
    ):
        self.broadcaster = broadcaster
        self.on_alert_persisted = on_alert_persisted

    def handle_detection(self, alert: Alert, flow: Flow, prediction: PredictionResponse) -> None:
        """
        Persist one detection and broadcast it. This is the method passed
        as `DetectionService(on_alert_generated=alert_service.handle_detection)`.
        """
        try:
            with session_scope() as db:
                self._persist_flow(db, flow)
                self._persist_alert(db, alert, flow, prediction)
                self._update_attack_statistics(db, alert)
        except Exception:  # noqa: BLE001 - a persistence failure must not crash the detection worker (the already-generated alert stays visible in-memory via DetectionService either way)
            logger.exception("Failed to persist detection for flow %s", flow.flow_id)
            return

        self.broadcaster.publish_alert_threadsafe(alert.model_dump())

        if self.on_alert_persisted is not None:
            try:
                self.on_alert_persisted({
                    "id": alert.id, "severity": alert.severity, "attack_type": alert.attack,
                    "source_ip": alert.source_ip, "destination_ip": alert.destination_ip, "flow_id": alert.flow_id,
                })
            except Exception:  # noqa: BLE001 - a subscriber's bug (e.g. the response engine) must never break alert persistence
                logger.exception("on_alert_persisted callback raised for alert %s", alert.id)

    @staticmethod
    def _persist_flow(db, flow: Flow) -> FlowHistory:
        row = FlowHistory(
            id=flow.flow_id,
            protocol=flow.protocol,
            source_ip=flow.src_ip,
            destination_ip=flow.dst_ip,
            source_port=flow.src_port,
            destination_port=flow.dst_port,
            start_time=datetime.fromtimestamp(flow.start_time, tz=timezone.utc),
            end_time=datetime.fromtimestamp(flow.last_seen, tz=timezone.utc),
            packet_count=flow.packet_count,
            byte_count=flow.byte_count,
        )
        return FlowRepository(db).create(row)

    @staticmethod
    def _persist_alert(db, alert: Alert, flow: Flow, prediction: PredictionResponse) -> AlertRow:
        # Reputation check for the source IP - this informs the threat_tag
        # and may influence the displayed severity without discarding a
        # genuinely malicious flow from a trusted source.
        reputation_result = _reputation_registry.check_ip(db, alert.source_ip)
        threat_tag = reputation_result.tag  # "Known Malicious" | "Suspicious" | "Unknown" | "Trusted"

        # Adjust severity based on reputation, but never fully suppress
        # detection for a trusted source - a truly malicious flow from a
        # trusted IP is still flagged, just with a reduced severity level
        # so the operator can review.
        severity = alert.severity  # default to the model's verdict
        if threat_tag == "Trusted" and alert.confidence >= 80:
            severity = "Low"
        elif threat_tag == "Trusted" and alert.confidence < 80:
            severity = "Legitimate"
        elif threat_tag == "Known Malicious":
            severity = alert.severity  # keep original
        elif threat_tag == "Suspicious":
            severity = alert.severity  # keep original

        row = AlertRow(
            id=alert.id,
            timestamp=datetime.fromisoformat(alert.timestamp),
            attack_type=alert.attack,
            confidence=alert.confidence,
            severity=severity,
            source_ip=alert.source_ip,
            destination_ip=alert.destination_ip,
            protocol=alert.protocol,
            flow_id=alert.flow_id,
            packet_count=flow.packet_count,
            bytes=flow.byte_count,
            status="new",
            model_version=alert.model_version,
            processing_time_ms=prediction.latency_ms,
            threat_tag=threat_tag,
        )
        return AlertRepository(db).create(row)

    @staticmethod
    def _update_attack_statistics(db, alert: Alert) -> None:
        AttackStatisticsRepository(db).upsert(
            attack_type=alert.attack,
            confidence=alert.confidence,
            seen_at=datetime.fromisoformat(alert.timestamp),
        )


# Process-wide instance. Wire it into a live capture pipeline with:
#   DetectionService(on_alert_generated=alert_service.handle_detection)
# Milestone 8 wires alert_service.on_alert_persisted = response_service.handle_alert
# in main.py's lifespan, not here, so this module stays decoupled from response_engine.
alert_service = AlertService()