"""
Capture endpoints for starting, stopping, and checking the status of live packet capture.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, status

from backend.auth.dependencies import get_current_user
from backend.auth.models import User
from backend.packet_capture.packet_filter import PacketFilterConfig, build_bpf_filter
from backend.services.capture_service import capture_service
from backend.packet_capture.interface import network_interfaces

router = APIRouter()

VALID_PROTOCOLS = {"tcp", "udp", "icmp"}
ALL_PROTOCOLS = "all"


class NetworkInterfaceResponse(BaseModel):
    """One selectable capture adapter. `name` is the raw handler scapy binds to; `description` is the human-readable label."""

    name: str
    description: str


class StartCaptureRequest(BaseModel):
    interface: Optional[str] = None
    backend: str = "scapy"
    bpf_filter: Optional[str] = None
    protocols: List[str] = Field(
        default_factory=lambda: ["tcp", "udp"],
        description="Transport protocols to capture (tcp/udp/icmp). Ignored when bpf_filter is given.",
    )


@router.get("/interfaces", response_model=List[NetworkInterfaceResponse], summary="List available network interfaces")
async def get_interfaces(user: User = Depends(get_current_user)) -> List[NetworkInterfaceResponse]:
    return [NetworkInterfaceResponse(**item) for item in network_interfaces()]


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

    raw_protocols = [p.lower() for p in req.protocols]
    unknown = [p for p in raw_protocols if p not in VALID_PROTOCOLS and p != ALL_PROTOCOLS]
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported protocol(s): {unknown}. Valid: {sorted(VALID_PROTOCOLS)} or '{ALL_PROTOCOLS}'",
        )
    if ALL_PROTOCOLS in raw_protocols:
        # "all" bypasses the transport-clause filter and captures the full
        # IEEE/IP traffic mix; the parser still only forwards the TCP/UDP/ICMP
        # packets CIC-IDS2017 flows represent.
        protocols: tuple[str, ...] = ()
    else:
        protocols = tuple(raw_protocols)

    filter_config = PacketFilterConfig(protocols=protocols)
    capture_service.start_capture(
        interface=req.interface,
        backend=req.backend,
        filter_config=filter_config,
        bpf_filter=req.bpf_filter.strip() if req.bpf_filter and req.bpf_filter.strip() else None,
    )
    return {"message": "Capture started", "bpf_filter": build_bpf_filter(filter_config)}


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
