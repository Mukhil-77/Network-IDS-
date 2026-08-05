"""
Quarantine/unquarantine host actions.

Unlike block_ip (which has a real, implementable live path via iptables),
"quarantine a host" typically means isolating it at the network switch/VLAN
level - infrastructure this project has no access to and no abstraction
for. Live mode for this action is therefore intentionally NOT implemented:
it always simulates, regardless of ENABLE_LIVE_RESPONSE_ACTIONS, and says
so explicitly rather than silently no-op'ing as if it worked.
"""

from __future__ import annotations

import time

from backend.response_engine.response_registry import ActionResult, ResponseContext, register_action
from backend.utils.logger import get_logger

logger = get_logger(__name__)


def quarantine_host(context: ResponseContext) -> ActionResult:
    start = time.perf_counter()
    ip = context.source_ip

    # No live implementation exists (see module docstring) - always
    # simulated, and the message says so rather than implying real action.
    message = f"[SIMULATION] Would isolate host {ip} at the network layer (VLAN/switch-port quarantine not implemented in this environment)"
    logger.info("quarantine_host(%s) - simulated only", ip)

    return ActionResult(
        action="quarantine_host", status="success", message=message,
        rollback_available=True, execution_time_ms=(time.perf_counter() - start) * 1000,
        metadata={"ip": ip, "mode": "simulation"},
    )


def unquarantine_host(context: ResponseContext) -> ActionResult:
    start = time.perf_counter()
    ip = context.source_ip
    message = f"[SIMULATION] Would restore host {ip} to normal network access"
    logger.info("unquarantine_host(%s) - simulated only", ip)

    return ActionResult(
        action="unquarantine_host", status="success", message=message,
        rollback_available=False, execution_time_ms=(time.perf_counter() - start) * 1000,
        metadata={"ip": ip, "mode": "simulation"},
    )


register_action("quarantine_host", quarantine_host)
register_action("unquarantine_host", unquarantine_host, rollback_of="quarantine_host")
