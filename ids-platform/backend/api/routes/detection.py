"""
Detection control endpoints.

Thin control plane over the capture -> flow -> predict -> alert pipeline
(backend/services/capture_service.py wires DetectionService + FlowManager +
PacketCapture; this module exposes start/stop/status over HTTP, mirroring
the capture endpoints but reporting on the *detection* side - including the
alerts the pipeline has generated in-memory).

Endpoints:
    POST   /detection/start            Start capture + detection on an interface
    POST   /detection/stop             Stop capture + detection
    GET    /detection/status           Pipeline status + stats
    GET    /detection/alerts/recent    Most recent in-memory alerts
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from backend.auth.dependencies import get_current_user
from backend.auth.models import User
from backend.services.capture_service import capture_service

router = APIRouter(prefix="/detection", tags=["Detection"])


class StartDetectionRequest(BaseModel):
    interface: Optional[str] = None
    backend: str = "scapy"
    bpf_filter: Optional[str] = None


@router.post("/start", summary="Start the detection pipeline (capture -> flow -> predict -> alert)")
async def start_detection(
    req: StartDetectionRequest,
    user: User = Depends(get_current_user),
) -> Dict[str, str]:
    if capture_service.capture is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Detection pipeline is already running",
        )
    capture_service.start_capture(interface=req.interface, backend=req.backend)
    return {"message": "Detection pipeline started", "interface": req.interface or "any"}


@router.post("/stop", summary="Stop the detection pipeline")
async def stop_detection(user: User = Depends(get_current_user)) -> Dict[str, str]:
    if capture_service.capture is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Detection pipeline is not running",
        )
    capture_service.stop_capture()
    return {"message": "Detection pipeline stopped"}


@router.get("/status", summary="Detection pipeline status and statistics")
async def detection_status(user: User = Depends(get_current_user)) -> Dict[str, Any]:
    status_data = capture_service.get_status()
    status_data["recent_alerts"] = len(capture_service.detection_service.get_recent_alerts(100))
    return status_data


@router.get("/alerts/recent", summary="Most recent alerts generated in-memory by the detection pipeline")
async def recent_alerts(
    limit: int = 50,
    user: User = Depends(get_current_user),
) -> list[Dict[str, Any]]:
    alerts = capture_service.detection_service.get_recent_alerts(limit)
    return [alert.model_dump() for alert in alerts]


@router.get("/packets/recent", summary="Most recent packets seen by the capture pipeline (in-memory live feed)")
async def recent_packets(
    limit: int = 100,
    user: User = Depends(get_current_user),
) -> list[Dict[str, Any]]:
    return capture_service.get_recent_packets(limit)
