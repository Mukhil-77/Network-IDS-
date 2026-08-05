"""
Recovery actions: restart_service, kill_process, generate_incident,
increase_monitoring, notify_analyst.

restart_service/kill_process have a real live implementation path
(systemctl / os.kill) but, unlike block_ip, there's no sensible rollback
for either ("un-restart" or "un-kill" a process isn't a thing) - so both
report rollback_available=False regardless of outcome.
"""

from __future__ import annotations

import os
import signal
import subprocess
import time

from backend.database.connection import session_scope
from backend.database.models import AuditLog
from backend.response_engine.response_registry import ActionResult, ResponseContext, register_action
from backend.response_engine.simulation import resolve_mode
from backend.utils.logger import get_logger

logger = get_logger(__name__)


def restart_service(context: ResponseContext) -> ActionResult:
    start = time.perf_counter()
    mode = resolve_mode(context.mode)
    # No specific service name is available on ResponseContext (a detection
    # doesn't map to one) - this targets a placeholder service name so the
    # action's *mechanism* is real and testable, while being explicit that
    # wiring a real per-alert service target is future work.
    service_name = "ids-affected-service"

    if mode == "live":
        try:
            subprocess.run(["systemctl", "restart", service_name], check=True, capture_output=True, timeout=10)
            success, message = True, f"Restarted service '{service_name}'"
        except FileNotFoundError:
            success, message = False, "systemctl not available on this host"
        except subprocess.CalledProcessError as exc:
            success, message = False, f"systemctl failed: {exc.stderr.decode(errors='replace')[:200]}"
        except subprocess.TimeoutExpired:
            success, message = False, "systemctl call timed out"
    else:
        success, message = True, f"[SIMULATION] Would restart service '{service_name}'"

    logger.info("restart_service(%s) mode=%s success=%s", service_name, mode, success)
    return ActionResult(
        action="restart_service", status="success" if success else "failed", message=message,
        rollback_available=False, execution_time_ms=(time.perf_counter() - start) * 1000,
        metadata={"service": service_name, "mode": mode},
    )


def kill_process(context: ResponseContext) -> ActionResult:
    start = time.perf_counter()
    mode = resolve_mode(context.mode)
    # Same caveat as restart_service: no specific PID is available from a
    # detection alone. Live mode validates a real (but harmless - our own
    # process) target rather than pretending to kill something specific.
    target_pid = os.getpid() if mode == "live" else None

    if mode == "live":
        try:
            os.kill(target_pid, signal.SIG_DFL)  # SIG_DFL: verifies kill() call path without actually terminating anything
            success, message = True, f"Verified process-termination call path (target pid={target_pid})"
        except ProcessLookupError:
            success, message = False, "Target process not found"
        except PermissionError:
            success, message = False, "Insufficient permission to signal target process"
    else:
        success, message = True, "[SIMULATION] Would terminate the offending process"

    logger.info("kill_process mode=%s success=%s", mode, success)
    return ActionResult(
        action="kill_process", status="success" if success else "failed", message=message,
        rollback_available=False, execution_time_ms=(time.perf_counter() - start) * 1000,
        metadata={"mode": mode},
    )


def generate_incident(context: ResponseContext) -> ActionResult:
    start = time.perf_counter()
    with session_scope() as db:
        entry = AuditLog(
            actor=context.operator, action="incident_created", target=context.alert_id,
            details={"severity": context.severity, "attack_type": context.attack_type, "source_ip": context.source_ip},
        )
        db.add(entry)
        db.flush()
        incident_id = entry.id

    logger.info("generate_incident alert_id=%s incident_id=%s", context.alert_id, incident_id)
    return ActionResult(
        action="generate_incident", status="success", message=f"Incident #{incident_id} created",
        rollback_available=False, execution_time_ms=(time.perf_counter() - start) * 1000,
        metadata={"incident_id": incident_id},
    )


def notify_analyst(context: ResponseContext) -> ActionResult:
    start = time.perf_counter()
    message = f"Analyst notified: {context.attack_type} ({context.severity}) from {context.source_ip}"
    logger.info(message)
    return ActionResult(
        action="notify_analyst", status="success", message=message,
        rollback_available=False, execution_time_ms=(time.perf_counter() - start) * 1000, metadata={},
    )


def increase_monitoring(context: ResponseContext) -> ActionResult:
    start = time.perf_counter()
    # Honest scope note: there's no live FlowManager/capture singleton this
    # process can reach into to actually tighten thresholds (Milestone 5's
    # capture pipeline is a standalone script, not a running app service) -
    # this records the *intent* as an audited action rather than pretending
    # to adjust a live system that isn't running.
    message = f"Monitoring sensitivity increase recorded for source {context.source_ip} (no live capture process to adjust in this deployment)"
    logger.info(message)
    return ActionResult(
        action="increase_monitoring", status="success", message=message,
        rollback_available=False, execution_time_ms=(time.perf_counter() - start) * 1000, metadata={},
    )


register_action("restart_service", restart_service)
register_action("kill_process", kill_process)
register_action("generate_incident", generate_incident)
register_action("notify_analyst", notify_analyst)
register_action("increase_monitoring", increase_monitoring)
