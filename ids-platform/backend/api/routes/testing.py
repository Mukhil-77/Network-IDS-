"""
Attack simulation endpoints: generate synthetic attack alerts to validate
the detection -> alert -> response pipeline end to end.

The simulation logic lives in backend/services/testing_service.py
(TestingService) - this module is a thin HTTP layer over it.

    POST /testing/simulate   Create a simulated attack alert
    GET  /testing/history    Recent simulation history
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend.auth.dependencies import get_current_user
from backend.auth.models import User
from backend.services.testing_service import SUPPORTED_ATTACK_TYPES, testing_service

router = APIRouter(prefix="/testing", tags=["Testing"])


class SimulateAttackRequest(BaseModel):
    attack_type: str = Field("port_scan", description="One of: " + ", ".join(sorted(SUPPORTED_ATTACK_TYPES)))
    confidence: float = Field(0.99, ge=0.0, le=1.0)
    source_ip: str = "192.168.1.100"
    destination_ip: str = "10.0.0.5"
    protocol: str = "TCP"
    severity: Optional[str] = None  # defaults to the attack type's profile severity


@router.post("/simulate", summary="Simulate an attack alert through the full pipeline")
async def simulate_attack(
    req: SimulateAttackRequest,
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    if req.attack_type not in SUPPORTED_ATTACK_TYPES:
        req.attack_type = "custom"

    result = testing_service.simulate_attack(
        attack_type=req.attack_type,
        confidence=req.confidence,
        source_ip=req.source_ip,
        destination_ip=req.destination_ip,
        protocol=req.protocol,
        severity=req.severity,
        operator=user.username,
    )
    result["user"] = user.username
    return result


@router.get("/history", summary="Get attack simulation history")
async def get_simulation_history(
    limit: int = 50,
    user: User = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """Return the recent history of simulated attacks."""
    return testing_service.get_history(limit)
