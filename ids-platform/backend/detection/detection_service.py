"""
Flow closed -> classify (off-thread) -> Alert.

FlowManager invokes its `on_flow_closed` callback from its own background
timeout-checking thread (or, for FIN/RST-terminated flows, from whichever
thread called `add_packet()` - see flow_manager.py). Running model inference
directly on that thread would block flow management/packet capture while
sklearn's predict() runs. DetectionService avoids that by submitting each
classification to a small ThreadPoolExecutor and returning immediately -
"non-blocking inference" from the spec.

    FlowManager.on_flow_closed(flow)
        v
    DetectionService.handle_flow_closed(flow)   <- returns immediately
        v  (submitted to executor, runs on a worker thread)
    Detector.classify_flow(flow)
        v
    build_alert(flow, prediction)
        v
    _store_alert()  (thread-safe, bounded, in-memory for this milestone -
                      a real store is Milestone 7's job)
"""

from __future__ import annotations

import threading
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Optional

from backend.detection.alert import Alert, build_alert
from backend.detection.detector import Detector
from backend.ml.artifacts import ArtifactNotFoundError
from backend.ml.schemas import PredictionResponse
from backend.packet_capture.flow_manager import Flow
from backend.services.prediction_service import PredictionService, prediction_service as default_prediction_service
from backend.utils.logger import get_logger

logger = get_logger(__name__)

DEFAULT_MAX_STORED_ALERTS = 1000

# See DetectionService.__init__'s on_alert_generated parameter.
OnAlertGenerated = Callable[[Alert, Flow, PredictionResponse], None]


class DetectionService:
    """
    Wires flow completion to classification and alert generation.

    Usage:
        detection_service = DetectionService()
        flow_manager = FlowManager(on_flow_closed=detection_service.handle_flow_closed)
        capture = PacketCapture(flow_manager=flow_manager, ...)
        capture.start()
        ...
        alerts = detection_service.get_recent_alerts(50)
    """

    def __init__(
        self,
        prediction_service: Optional[PredictionService] = None,
        max_workers: int = 4,
        max_stored_alerts: int = DEFAULT_MAX_STORED_ALERTS,
        on_alert_generated: Optional[OnAlertGenerated] = None,
    ):
        self.detector = Detector(prediction_service or default_prediction_service)
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="detection-worker")
        self._alerts: deque[Alert] = deque(maxlen=max_stored_alerts)
        self._alerts_lock = threading.Lock()
        # Milestone 6 extension point: fired with (alert, flow, prediction)
        # after an alert is generated and stored in-memory, so a subscriber
        # (alert_service.py) can persist it and broadcast it over
        # WebSocket - additive, defaults to None, so nothing changes for
        # any existing caller that doesn't pass it.
        self.on_alert_generated = on_alert_generated

    def handle_flow_closed(self, flow: Flow) -> None:
        """
        FlowManager's on_flow_closed callback. Submits classification to the
        executor and returns immediately - never blocks the calling thread.
        """
        self._executor.submit(self._classify_and_store, flow)

    def _classify_and_store(self, flow: Flow) -> None:
        try:
            prediction, report = self.detector.classify_flow(flow)
        except ArtifactNotFoundError:
            logger.warning("Skipped classifying flow %s: no trained model available", flow.flow_id)
            return
        except Exception:  # noqa: BLE001 - one bad flow must never kill a worker thread silently
            logger.exception("Classification failed for flow %s", flow.flow_id)
            return

        alert = build_alert(flow, prediction)
        self._store_alert(alert)

        logger.info(
            "Alert generated: id=%s attack=%s severity=%s confidence=%.2f%% %s:%d -> %s:%d",
            alert.id, alert.attack, alert.severity, alert.confidence,
            alert.source_ip, alert.source_port, alert.destination_ip, alert.destination_port,
        )

        if self.on_alert_generated is not None:
            try:
                self.on_alert_generated(alert, flow, prediction)
            except Exception:  # noqa: BLE001 - a subscriber's bug must never break a detection worker
                logger.exception("on_alert_generated callback raised for alert %s", alert.id)

    def _store_alert(self, alert: Alert) -> None:
        with self._alerts_lock:
            self._alerts.append(alert)  # deque(maxlen=...) bounds memory automatically

    def get_recent_alerts(self, limit: Optional[int] = None) -> list[Alert]:
        """Most-recent-first list of generated alerts, optionally capped to `limit`."""
        with self._alerts_lock:
            alerts = list(reversed(self._alerts))
        return alerts[:limit] if limit is not None else alerts

    def shutdown(self) -> None:
        self._executor.shutdown(wait=True)
