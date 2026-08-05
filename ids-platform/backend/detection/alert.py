"""
Structured detection alerts.

An Alert is produced once per completed flow that the model classifies -
including BENIGN ones, so downstream consumers (a future dashboard,
database, or alert-suppression rule) can decide what counts as "alert
worthy" rather than that decision being made silently here.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from pydantic import BaseModel, Field

from backend.ml.schemas import PredictionResponse
from backend.packet_capture.flow_manager import Flow


class Alert(BaseModel):
    """One flow's classification result, in the shape the spec requires plus a few additive fields."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    attack: str
    severity: str
    confidence: float
    source_ip: str
    destination_ip: str
    protocol: str
    flow_id: str

    # Additive, not in the original spec example - kept because a
    # dashboard/alert list is far less useful without ports and a way to
    # tell which trained model version produced the call.
    source_port: int
    destination_port: int
    model_version: str

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "3f2a9c10-...",
                "timestamp": "2026-07-23T12:34:06Z",
                "attack": "DoS",
                "severity": "High",
                "confidence": 99.2,
                "source_ip": "10.0.0.5",
                "destination_ip": "10.0.0.10",
                "protocol": "TCP",
                "flow_id": "b7e1...",
                "source_port": 51322,
                "destination_port": 80,
                "model_version": "v1",
            }
        }
    }


def build_alert(flow: Flow, prediction: PredictionResponse) -> Alert:
    """Combine a completed Flow with its PredictionResponse into one Alert."""
    return Alert(
        attack=prediction.prediction,
        severity=prediction.severity,
        confidence=prediction.confidence,
        source_ip=flow.src_ip,
        destination_ip=flow.dst_ip,
        protocol=flow.protocol,
        flow_id=flow.flow_id,
        source_port=flow.src_port,
        destination_port=flow.dst_port,
        model_version=prediction.model_version,
    )
