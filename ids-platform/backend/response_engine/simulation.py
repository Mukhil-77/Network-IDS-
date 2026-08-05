"""
The one place "should this action actually do something destructive?" is
decided. Every action handler in firewall.py/quarantine.py/recovery.py
calls `resolve_mode()` before doing anything live-mode-only, rather than
each handler re-implementing this check - a single, auditable safety gate.

Two independent gates must both agree before a "live" request actually
executes live:
    1. The policy/API caller asked for mode="live" (ResponseContext.mode).
    2. Settings.ENABLE_LIVE_RESPONSE_ACTIONS is true (an operator, not a
       policy file or an API request, controls this - see core/config.py).

If either says no, the action runs in simulation - it logs what it *would*
do and returns success, without touching a firewall, process, or service.
This is the "Do NOT execute destructive actions by default" requirement,
enforced structurally rather than by convention.
"""

from backend.core.config import get_settings
from backend.utils.logger import get_logger

logger = get_logger(__name__)


def resolve_mode(requested_mode: str) -> str:
    """
    Returns "live" only if both gates above agree; otherwise returns
    "simulation" (even if `requested_mode` was "live") and logs why.
    """
    if requested_mode != "live":
        return "simulation"

    settings = get_settings()
    if not settings.ENABLE_LIVE_RESPONSE_ACTIONS:
        logger.warning(
            "Live response requested but ENABLE_LIVE_RESPONSE_ACTIONS is False - "
            "falling back to simulation. Set that setting explicitly to allow live actions."
        )
        return "simulation"

    return "live"


def is_simulation(requested_mode: str) -> bool:
    return resolve_mode(requested_mode) == "simulation"
