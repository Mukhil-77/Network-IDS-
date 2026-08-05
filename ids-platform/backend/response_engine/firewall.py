"""
Block/unblock IP actions.

Simulation mode (default, see simulation.py): records the intent to
`blocked_ips` (the placeholder table from Milestone 6 - this is the
milestone that finally writes to it) and logs it. No firewall is touched.

Live mode (requires an operator to explicitly set
ENABLE_LIVE_RESPONSE_ACTIONS=true): would shell out to `iptables`. That
call path is implemented for completeness but is untested in this
project's sandbox (no root / host network namespace access here) - see the
docstring on `_live_block_ip` for exactly what it does and why it's
guarded so heavily.
"""

from __future__ import annotations

import subprocess
import time

from backend.database.connection import session_scope
from backend.database.models import BlockedIP
from backend.response_engine.response_registry import ActionResult, ResponseContext, register_action
from backend.response_engine.simulation import resolve_mode
from backend.utils.logger import get_logger

logger = get_logger(__name__)


def _live_block_ip(ip: str) -> tuple[bool, str]:
    """
    Actually block `ip` via iptables. Only ever called when both of
    simulation.py's gates have already agreed to "live" - this function
    itself does no further safety checking, by design (one gate, checked
    once, upstream).
    """
    try:
        subprocess.run(
            ["iptables", "-A", "INPUT", "-s", ip, "-j", "DROP"],
            check=True, capture_output=True, timeout=5,
        )
        return True, f"iptables DROP rule added for {ip}"
    except FileNotFoundError:
        return False, "iptables not available on this host"
    except subprocess.CalledProcessError as exc:
        return False, f"iptables failed: {exc.stderr.decode(errors='replace')[:200]}"
    except subprocess.TimeoutExpired:
        return False, "iptables call timed out"


def _live_unblock_ip(ip: str) -> tuple[bool, str]:
    try:
        subprocess.run(
            ["iptables", "-D", "INPUT", "-s", ip, "-j", "DROP"],
            check=True, capture_output=True, timeout=5,
        )
        return True, f"iptables DROP rule removed for {ip}"
    except FileNotFoundError:
        return False, "iptables not available on this host"
    except subprocess.CalledProcessError as exc:
        return False, f"iptables failed: {exc.stderr.decode(errors='replace')[:200]}"
    except subprocess.TimeoutExpired:
        return False, "iptables call timed out"


def block_ip(context: ResponseContext) -> ActionResult:
    start = time.perf_counter()
    mode = resolve_mode(context.mode)
    ip = context.source_ip

    if mode == "live":
        success, message = _live_block_ip(ip)
    else:
        success, message = True, f"[SIMULATION] Would block source IP {ip} at the firewall"

    with session_scope() as db:
        db.add(BlockedIP(ip_address=ip, reason=f"{context.attack_type} ({context.severity})", is_active=True))

    logger.info("block_ip(%s) mode=%s success=%s", ip, mode, success)
    return ActionResult(
        action="block_ip", status="success" if success else "failed", message=message,
        rollback_available=success, execution_time_ms=(time.perf_counter() - start) * 1000,
        metadata={"ip": ip, "mode": mode},
    )


def unblock_ip(context: ResponseContext) -> ActionResult:
    start = time.perf_counter()
    mode = resolve_mode(context.mode)
    ip = context.source_ip

    if mode == "live":
        success, message = _live_unblock_ip(ip)
    else:
        success, message = True, f"[SIMULATION] Would unblock source IP {ip}"

    with session_scope() as db:
        row = db.query(BlockedIP).filter(BlockedIP.ip_address == ip, BlockedIP.is_active.is_(True)).first()
        if row is not None:
            row.is_active = False

    logger.info("unblock_ip(%s) mode=%s success=%s", ip, mode, success)
    return ActionResult(
        action="unblock_ip", status="success" if success else "failed", message=message,
        rollback_available=False, execution_time_ms=(time.perf_counter() - start) * 1000,
        metadata={"ip": ip, "mode": mode},
    )


register_action("block_ip", block_ip)
register_action("unblock_ip", unblock_ip, rollback_of="block_ip")
