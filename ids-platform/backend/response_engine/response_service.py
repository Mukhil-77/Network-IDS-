"""
The response workflow, end to end, exactly as the spec's diagram:

    Threat Detected
      v
    Determine Severity        (ResponseContext.severity, from the alert)
      v
    Select Response Policy    (policy_engine.get_actions(severity))
      v
    Execute Actions           (response_executor.execute_actions)
      v
    Record Result             (response_history.record_result, one row per action)
      v
    Update Alert Status       (AlertRow.status)
      v
    Notify Dashboard          (WebSocket: response_started/completed/failed)

Two entry points:
    handle_alert()    - automatic trigger, wired as AlertService's
                         on_alert_persisted callback (see alert_service.py's
                         one new attribute) - fires for every alert, letting
                         the policy for that severity decide what (if
                         anything) happens.
    execute_manual()  - POST /responses/execute - an analyst explicitly
                         triggering a response (optionally with a specific
                         action list, overriding the policy).
"""

from __future__ import annotations

from typing import Optional

from backend.database.connection import session_scope
from backend.database.models import Alert as AlertRow
from backend.database.models import ResponseHistory
from backend.response_engine import response_history
from backend.response_engine.response_executor import execute_actions
from backend.response_engine.response_registry import ResponseContext, ensure_actions_loaded, get_rollback_action
from backend.response_engine.response_rules import PolicyEngine, policy_engine as default_policy_engine
from backend.utils.logger import get_logger
from backend.websocket.broadcaster import AlertBroadcaster, broadcaster as default_broadcaster
from backend.websocket.events import WSEventType

logger = get_logger(__name__)

ensure_actions_loaded()


class ResponseService:
    def __init__(
        self,
        policy_engine: PolicyEngine = default_policy_engine,
        broadcaster: AlertBroadcaster = default_broadcaster,
    ):
        self.policy_engine = policy_engine
        self.broadcaster = broadcaster

    # ------------------------------------------------------------------
    # Automatic trigger (wired to AlertService.on_alert_persisted)
    # ------------------------------------------------------------------

    def handle_alert(self, alert_summary: dict) -> list[ResponseHistory]:
        """
        `alert_summary`: {id, severity, attack_type, source_ip,
        destination_ip, flow_id} - a plain dict snapshot (not a live ORM
        object - see alert_service.py) of a just-persisted alert.
        """
        actions = self.policy_engine.get_actions(alert_summary["severity"])
        if not actions:
            logger.info("No response actions configured for severity '%s'; nothing to do for alert %s", alert_summary["severity"], alert_summary["id"])
            return []

        mode = "simulation" if self.policy_engine.is_simulation_mode() else "live"
        return self._run(alert_summary, actions, mode, operator="automated")

    # ------------------------------------------------------------------
    # Manual trigger (POST /responses/execute)
    # ------------------------------------------------------------------

    def execute_manual(
        self,
        alert_summary: dict,
        actions: Optional[list[str]] = None,
        mode: Optional[str] = None,
        operator: str = "analyst",
    ) -> list[ResponseHistory]:
        resolved_actions = actions if actions is not None else self.policy_engine.get_actions(alert_summary["severity"])
        resolved_mode = mode if mode is not None else ("simulation" if self.policy_engine.is_simulation_mode() else "live")
        return self._run(alert_summary, resolved_actions, resolved_mode, operator=operator)

    # ------------------------------------------------------------------
    # Shared execution path
    # ------------------------------------------------------------------

    def _run(self, alert_summary: dict, actions: list[str], mode: str, operator: str) -> list[ResponseHistory]:
        alert_id = alert_summary["id"]
        group_id = response_history.new_group_id()

        context = ResponseContext(
            alert_id=alert_id, severity=alert_summary["severity"], attack_type=alert_summary["attack_type"],
            source_ip=alert_summary["source_ip"], destination_ip=alert_summary["destination_ip"],
            flow_id=alert_summary.get("flow_id"), mode=mode, operator=operator,
        )

        self._broadcast(WSEventType.RESPONSE_STARTED, {
            "response_group_id": group_id, "alert_id": alert_id, "actions": actions, "mode": mode,
        })

        results = execute_actions(actions, context)

        rows: list[ResponseHistory] = []
        row_ids: list[str] = []
        with session_scope() as db:
            for result in results:
                row = response_history.record_result(db, group_id, alert_id, result, mode, operator)
                rows.append(row)
                row_ids.append(row.id)  # captured while still attached to this session
            self._update_alert_status(db, alert_id, results)

        for result, row_id in zip(results, row_ids):
            event_type = WSEventType.RESPONSE_COMPLETED if result.status == "success" else WSEventType.RESPONSE_FAILED
            self._broadcast(event_type, {
                "response_id": row_id, "response_group_id": group_id, "alert_id": alert_id,
                "action": result.action, "status": result.status, "message": result.message, "mode": mode,
            })

        return rows

    @staticmethod
    def _update_alert_status(db, alert_id: str, results) -> None:
        alert_row = db.get(AlertRow, alert_id)
        if alert_row is None:
            return
        if not results:
            return
        if all(r.status == "success" for r in results):
            alert_row.status = "responded"
        elif any(r.status == "success" for r in results):
            alert_row.status = "partially_responded"
        else:
            alert_row.status = "response_failed"

    # ------------------------------------------------------------------
    # Rollback (POST /responses/rollback)
    # ------------------------------------------------------------------

    def rollback(self, response_id: str, operator: str = "analyst") -> ResponseHistory:
        """
        Raises:
            ValueError: If the response doesn't exist, has no rollback
                action, or was already rolled back.
        """
        from backend.database.repositories.responses import ResponseRepository

        # Step 1: read what we need in one short session, then let it close
        # BEFORE executing the rollback action - the action itself may open
        # its own session_scope() (e.g. firewall.unblock_ip), and holding
        # this outer session open across that call is exactly the nested-
        # transaction hazard that caused a real bug here during testing.
        with session_scope() as db:
            original = ResponseRepository(db).get(response_id)
            if original is None:
                raise ValueError(f"Response '{response_id}' not found")
            if not original.rollback_available:
                raise ValueError(f"Response '{response_id}' (action='{original.action}') has no rollback action")
            if original.rolled_back:
                raise ValueError(f"Response '{response_id}' was already rolled back")

            rollback_action = get_rollback_action(original.action)
            if rollback_action is None:
                raise ValueError(f"No rollback action registered for '{original.action}'")

            alert_row = db.get(AlertRow, original.alert_id)
            if alert_row is None:
                raise ValueError(f"Alert '{original.alert_id}' for this response no longer exists")

            original_group_id = original.response_group_id
            original_alert_id = original.alert_id
            original_mode = original.mode
            context = ResponseContext(
                alert_id=alert_row.id, severity=alert_row.severity, attack_type=alert_row.attack_type,
                source_ip=alert_row.source_ip, destination_ip=alert_row.destination_ip,
                flow_id=alert_row.flow_id, mode=original_mode, operator=operator,
            )

        # Step 2: execute the rollback action with no session held open.
        result = execute_actions([rollback_action], context)[0]

        # Step 3: a fresh, short session to record the result and mark the original rolled back.
        with session_scope() as db:
            rollback_row = response_history.record_result(db, original_group_id, original_alert_id, result, original_mode, operator)
            original_row = db.get(ResponseHistory, response_id)
            if original_row is not None:
                original_row.rolled_back = True

        self._broadcast(WSEventType.ROLLBACK_COMPLETED, {
            "response_id": rollback_row.id, "original_response_id": response_id,
            "action": result.action, "status": result.status, "message": result.message,
        })
        return rollback_row

    def _broadcast(self, event_type: str, payload: dict) -> None:
        self.broadcaster.publish_event_threadsafe(event_type, payload)


# Process-wide instance - routes and main.py's AlertService wiring both import this.
response_service = ResponseService()
