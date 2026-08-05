"""
Runs an ordered list of action names against one ResponseContext, action by
action, catching each action's own exceptions so one failing action (e.g. a
network call in send_email) never prevents the rest of the policy from
running.
"""

from __future__ import annotations

import time

from backend.response_engine.response_registry import ActionResult, ResponseContext, get_handler
from backend.utils.logger import get_logger

logger = get_logger(__name__)


def execute_actions(action_names: list[str], context: ResponseContext) -> list[ActionResult]:
    results: list[ActionResult] = []

    for name in action_names:
        handler = get_handler(name)
        if handler is None:
            logger.error("No registered handler for action '%s' - skipping", name)
            results.append(ActionResult(action=name, status="failed", message=f"Unknown action '{name}'"))
            continue

        start = time.perf_counter()
        try:
            result = handler(context)
        except Exception as exc:  # noqa: BLE001 - one action's bug must not abort the rest of the policy
            elapsed = (time.perf_counter() - start) * 1000
            logger.exception("Action '%s' raised while executing for alert %s", name, context.alert_id)
            result = ActionResult(action=name, status="failed", message=str(exc), execution_time_ms=elapsed)

        results.append(result)

    return results
