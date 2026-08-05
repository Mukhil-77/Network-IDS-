"""
Capture endpoints for starting, stopping, and checking the status of live packet capture.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, status

from backend.auth.dependencies import get_current_user
from backend.auth.models import User
from backend.services.capture_service import capture_service
from backend.packet_capture.interface import list_interfaces

router = APIRouter()


class StartCaptureRequest(BaseModel):
    interface: Optional[str] = None
    backend: str = "scapy"
    bpf_filter: Optional[str] = None


@router.get("/interfaces", response_model=List[str], summary="List available network interfaces")
async def get_interfaces(user: User = Depends(get_current_user)) -> List[str]:
    return list_interfaces()


@router.post("/start", summary="Start packet capture")
async def start_capture(
    req: StartCaptureRequest,
    user: User = Depends(get_current_user)
) -> Dict[str, str]:
    if capture_service.capture is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Capture is already running"
        )
    
    # In a real app we'd construct a PacketFilterConfig from bpf_filter if needed
    capture_service.start_capture(
        interface=req.interface,
        backend=req.backend
    )
    return {"message": "Capture started"}


@router.post("/stop", summary="Stop packet capture")
async def stop_capture(user: User = Depends(get_current_user)) -> Dict[str, str]:
    if capture_service.capture is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Capture is not running"
        )
        
    capture_service.stop_capture()
    return {"message": "Capture stopped"}


@router.get("/status", summary="Get capture status")
async def capture_status(user: User = Depends(get_current_user)) -> Dict[str, Any]:
    return capture_service.get_status()
