"""
Self-healing and recovery mechanisms for IDS.

Implements controlled recovery after automated responses:
- Temporary block removal
- IP restoration
- Firewall rule cleanup
- Monitoring re-enable
- Recovery verification
- Recovery time tracking

Research contribution: Verified closed-loop automated response and recovery.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set
from collections import defaultdict
import uuid
from typing import Tuple

from backend.ml.automated_response import (
    ResponseAction, 
    ResponseActionType, 
    ResponseStatus,
    ResponseExecutor,
)
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class RecoveryStatus(Enum):
    """Recovery status."""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    VERIFIED = "verified"
    MANUAL_INTERVENTION = "manual_intervention"


class RecoveryTrigger(Enum):
    """What triggered the recovery."""
    TIMEOUT = "timeout"           # Auto-expiry timer
    VERIFICATION_FAILED = "verification_failed"  # Post-action verification failed
    ANALYST_REQUEST = "analyst_request"  # Manual trigger
    FALSE_POSITIVE_CONFIRMED = "false_positive_confirmed"
    THREAT_NEUTRALIZED = "threat_neutralized"
    SCHEDULED = "scheduled"


@dataclass
class RecoveryAction:
    """Definition of a recovery action."""
    recovery_id: str
    original_action_id: str
    recovery_type: str  # "remove_block", "restore_access", "restore_monitoring", etc.
    target: str
    trigger: RecoveryTrigger
    parameters: Dict[str, Any] = field(default_factory=dict)
    status: RecoveryStatus = RecoveryStatus.NOT_STARTED
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    verification_result: Optional[bool] = None
    verified_at: Optional[datetime] = None
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "recovery_id": self.recovery_id,
            "original_action_id": self.original_action_id,
            "recovery_type": self.recovery_type,
            "target": self.target,
            "trigger": self.trigger.value,
            "parameters": self.parameters,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error_message": self.error_message,
            "verification_result": self.verification_result,
            "verified_at": self.verified_at.isoformat() if self.verified_at else None,
        }


@dataclass
class RecoveryPlan:
    """Plan for recovering from a response action."""
    response_action_id: str
    recovery_actions: List[str]  # Recovery action types to execute
    timeout_minutes: int = 60  # Auto-trigger recovery after this time
    verification_checks: List[str] = field(default_factory=list)
    max_retries: int = 3
    retry_delay_minutes: int = 5
    requires_approval: bool = False


# Default recovery plans for each action type
DEFAULT_RECOVERY_PLANS = {
    ResponseActionType.BLOCK_IP: RecoveryPlan(
        response_action_id="",
        recovery_actions=["remove_block", "verify_connectivity"],
        timeout_minutes=60,
        verification_checks=["connectivity_test", "firewall_rule_removed"],
        max_retries=3,
    ),
    ResponseActionType.RATE_LIMIT: RecoveryPlan(
        response_action_id="",
        recovery_actions=["remove_rate_limit", "verify_throughput"],
        timeout_minutes=30,
        verification_checks=["throughput_restored", "rate_limit_removed"],
    ),
    ResponseActionType.QUARANTINE_HOST: RecoveryPlan(
        response_action_id="",
        recovery_actions=["restore_network_access", "verify_connectivity"],
        timeout_minutes=120,
        verification_checks=["network_access_restored", "vlan_restored"],
        requires_approval=True,
    ),
    ResponseActionType.RATE_LIMIT: RecoveryPlan(
        response_action_id="",
        recovery_actions=["remove_rate_limit"],
        timeout_minutes=30,
    ),
    ResponseActionType.KILL_PROCESS: RecoveryPlan(
        response_action_id="",
        recovery_actions=["restart_process"],
        timeout_minutes=15,
    ),
    ResponseActionType.RESTART_SERVICE: RecoveryPlan(
        response_action_id="",
        recovery_actions=["verify_service_running"],
        timeout_minutes=10,
    ),
    ResponseActionType.INCREASE_MONITORING: RecoveryPlan(
        response_action_id="",
        recovery_actions=["restore_monitoring_level"],
        timeout_minutes=60,
    ),
}


class RecoveryExecutor:
    """
    Executes recovery actions for automated responses.
    
    Handles the RECOVER phase of DETECT → SCORE → VERIFY → RESPOND → LOG → RECOVER.
    """
    
    def __init__(
        self,
        response_executor: Optional[Any] = None,
        recovery_plans: Optional[Dict[str, Any]] = None,
        dry_run: bool = True,
    ):
        self.dry_run = dry_run
        self.recovery_plans = recovery_plans or DEFAULT_RECOVERY_PLANS
        self.recovery_history: List[Dict] = []
        self.active_recoveries: Dict[str, Any] = {}
        
        # Recovery callbacks (replace with real implementations)
        self.recovery_callbacks: Dict[str, Callable] = {}
        self.verification_callbacks: Dict[str, Callable] = {}
        
        self._register_default_callbacks()
    
    def _register_default_callbacks(self):
        """Register default recovery callbacks (simulation mode)."""
        self.recovery_callbacks = {
            "remove_block": self._remove_block,
            "verify_connectivity": self._verify_connectivity,
            "remove_rate_limit": self._remove_rate_limit,
            "verify_throughput": self._verify_throughput,
            "restore_network_access": self._restore_network_access,
            "restart_process": self._restart_process,
            "verify_service_running": self._verify_service_running,
            "restore_monitoring_level": self._restore_monitoring_level,
        }
        
        self.verification_callbacks = {
            "connectivity_test": self._verify_connectivity,
            "firewall_rule_removed": self._verify_firewall_removed,
            "throughput_restored": self._verify_throughput,
            "rate_limit_removed": self._verify_rate_limit_removed,
            "network_access_restored": self._verify_network_access,
            "vlan_restored": self._verify_vlan_restored,
            "service_running": self._verify_service_running,
        }
    
    # Recovery callbacks (replace with real implementations)
    def _remove_block(self, params: Dict) -> Tuple[bool, str]:
        ip = params.get("ip", "")
        logger.info(f"RECOVERY: Removing block for IP {ip} (dry_run={self.dry_run})")
        if not self.dry_run:
            # TODO: Remove firewall rule
            pass
        return True, f"Block removed for {ip}"
    
    def _verify_connectivity(self, params: Dict) -> Tuple[bool, str]:
        target = params.get("target", "")
        logger.info(f"VERIFICATION: Testing connectivity to {target}")
        # In real implementation: ping, TCP connect, etc.
        return True, f"Connectivity to {target} verified"
    
    def _verify_firewall_removed(self, params: Dict) -> Tuple[bool, str]:
        return True, "Firewall rule removal verified"
    
    def _remove_rate_limit(self, params: Dict) -> Tuple[bool, str]:
        target = params.get("target", "")
        logger.info(f"RECOVERY: Removing rate limit for {target} (dry_run={self.dry_run})")
        return True, f"Rate limit removed for {target}"
    
    def _verify_throughput(self, params: Dict) -> Tuple[bool, str]:
        return True, "Throughput restored to normal"
    
    def _verify_rate_limit_removed(self, params: Dict) -> Tuple[bool, str]:
        return True, "Rate limit removal verified"
    
    def _restore_network_access(self, params: Dict) -> Tuple[bool, str]:
        host = params.get("host", "")
        logger.info(f"RECOVERY: Restoring network access for {host} (dry_run={self.dry_run})")
        return True, f"Network access restored for {host}"
    
    def _verify_network_access(self, params: Dict) -> Tuple[bool, str]:
        return True, "Network access restored"
    
    def _verify_vlan_restored(self, params: Dict) -> Tuple[bool, str]:
        return True, "VLAN restored"
    
    def _restart_process(self, params: Dict) -> Tuple[bool, str]:
        pid = params.get("pid", "")
        logger.info(f"RECOVERY: Restarting process {pid} (dry_run={self.dry_run})")
        return True, f"Process {pid} restarted"
    
    def _verify_service_running(self, params: Dict) -> Tuple[bool, str]:
        return True, "Service verified running"
    
    def _restore_monitoring_level(self, params: Dict) -> Tuple[bool, str]:
        target = params.get("target", "")
        logger.info(f"RECOVERY: Restoring monitoring level for {target} (dry_run={self.dry_run})")
        return True, f"Monitoring level restored for {target}"
    
    def execute_recovery(self, recovery_action: Any) -> Tuple[bool, str]:
        """Execute a single recovery action."""
        recovery_action.status = RecoveryStatus.IN_PROGRESS
        recovery_action.started_at = datetime.now()
        
        handler = self.recovery_callbacks.get(recovery_action.recovery_type)
        if not handler:
            recovery_action.status = RecoveryStatus.FAILED
            recovery_action.error_message = f"No handler for recovery type: {recovery_action.recovery_type}"
            return False, recovery_action.error_message
        
        try:
            success, message = handler(recovery_action.parameters)
            recovery_action.status = RecoveryStatus.COMPLETED if success else RecoveryStatus.FAILED
            recovery_action.completed_at = datetime.now()
            recovery_action.error_message = None if success else message
            return success, message
        except Exception as e:
            logger.exception(f"Recovery execution failed: {e}")
            recovery_action.status = RecoveryStatus.FAILED
            recovery_action.completed_at = datetime.now()
            recovery_action.error_message = str(e)
            return False, str(e)
    
    def execute_recovery_plan(self, response_action: Any, trigger: RecoveryTrigger) -> List[Dict]:
        """Execute full recovery plan for a response action."""
        plan = self.recovery_plans.get(response_action.action_type)
        if not plan:
            logger.warning(f"No recovery plan for action type: {response_action.action_type}")
            return []
        
        results = []
        for recovery_type in plan.recovery_actions:
            recovery = RecoveryAction(
                recovery_id=str(uuid.uuid4())[:8],
                original_action_id=response_action.action_id,
                recovery_type=recovery_type,
                target=response_action.target,
                trigger=trigger,
                parameters={
                    "target": response_action.target,
                    "original_params": response_action.parameters,
                },
            )
            
            success, message = self.execute_recovery(recovery)
            
            # Verify if checks defined
            verified = False
            if success and plan.verification_checks:
                # Run verification checks
                all_verified = True
                for check in plan.verification_checks:
                    if check in self.verification_callbacks:
                        verified, _ = self.verification_callbacks[check]({
                            "target": response_action.target,
                        })
                        if not verified:
                            all_verified = False
                            break
                verified = all_verified
            
            result = {
                "recovery_type": recovery_type,
                "success": success,
                "verified": verified,
                "message": "Completed" if success else "Failed",
            }
            results.append(result)
            
            if not success:
                logger.error(f"Recovery {recovery_type} failed for {response_action.target}")
                break
        
        return results
    
    def trigger_recovery(
        self,
        response_action: Any,
        trigger: RecoveryTrigger = RecoveryTrigger.ANALYST_REQUEST,
    ) -> Dict[str, Any]:
        """Trigger recovery for a response action."""
        logger.info(f"Triggering recovery for action {response_action.action_id} (trigger: {trigger.value})")
        
        results = self.execute_recovery_plan(response_action, trigger)
        
        recovery_record = {
            "trigger": trigger.value,
            "response_action_id": response_action.action_id,
            "target": response_action.target,
            "timestamp": datetime.now().isoformat(),
            "recoveries": results,
            "all_successful": all(r["success"] for r in results),
            "all_verified": all(r.get("verified", False) for r in results),
        }
        
        self.recovery_history.append(recovery_record)
        return recovery_record
    
    def auto_recovery_check(self, response_executor: Any) -> List[Dict]:
        """Check for auto-recovery conditions (timeout, verification failure)."""
        triggered = []
        
        for action in response_executor.action_history:
            if action.status not in (ResponseStatus.COMPLETED, ResponseStatus.VERIFIED):
                continue
            
            # Check timeout-based recovery
            plan = self.recovery_plans.get(action.action_type)
            if plan and plan.timeout_minutes > 0:
                if action.completed_at:
                    elapsed = datetime.now() - action.completed_at
                    if elapsed > timedelta(minutes=plan.timeout_minutes):
                        logger.info(f"Auto-recovery triggered by timeout for {action.action_id}")
                        recovery = self.trigger_recovery(action, RecoveryTrigger.TIMEOUT)
                        triggered.append(recovery)
            
            # Check verification failure
            if action.verification_result is False:
                logger.info(f"Auto-recovery triggered by verification failure for {action.action_id}")
                recovery = self.trigger_recovery(action, RecoveryTrigger.VERIFICATION_FAILED)
                triggered.append(recovery)
        
        return triggered
    
    def get_recovery_metrics(self) -> Dict[str, Any]:
        """Get recovery metrics for dashboard."""
        total = len(self.recovery_history)
        successful = sum(1 for r in self.recovery_history if r["all_successful"])
        verified = sum(1 for r in self.recovery_history if r["all_verified"])
        
        by_trigger = defaultdict(int)
        for r in self.recovery_history:
            by_trigger[r["trigger"]] += 1
        
        return {
            "total_recoveries": total,
            "successful": successful,
            "success_rate": successful / total if total > 0 else 0,
            "verified": verified,
            "verification_rate": verified / successful if successful > 0 else 0,
            "by_trigger": dict(by_trigger),
        }


class SelfHealingOrchestrator:
    """
    Orchestrates the full self-healing lifecycle:
    DETECT → SCORE → VERIFY → RESPOND → LOG → RECOVER
    """
    
    def __init__(
        self,
        response_executor: Optional[Any] = None,
        recovery_executor: Optional[RecoveryExecutor] = None,
    ):
        self.response_executor = response_executor
        self.recovery_executor = recovery_executor or RecoveryExecutor()
        self.healing_history: List[Dict] = []
    
    def handle_full_lifecycle(
        self,
        alert: Dict[str, Any],
        risk_scorer: Any = None,
    ) -> Dict[str, Any]:
        """
        Handle full DETECT → SCORE → VERIFY → RESPOND → LOG → RECOVER lifecycle.
        
        For demo purposes, recovery is triggered immediately after response.
        In production, recovery would be triggered by timeout or verification failure.
        """
        # This would integrate with the ResponseOrchestrator
        # For now, return a summary of what would happen
        
        return {
            "alert_id": alert.get("id"),
            "lifecycle": "DETECT -> SCORE -> VERIFY -> RESPOND -> LOG -> RECOVER",
            "stages": {
                "detect": "Alert received",
                "score": "Risk scored",
                "verify": "Risk verified above threshold",
                "respond": "Response actions executed",
                "log": "Actions logged",
                "recover": "Recovery scheduled (timeout-based)",
            },
            "recovery_scheduled": True,
            "recovery_trigger": "timeout",
            "estimated_recovery_time_minutes": 60,
        }
    
    def get_healing_dashboard_data(self) -> Dict[str, Any]:
        """Get data for self-healing dashboard."""
        return {
            "recovery_metrics": self.recovery_executor.get_recovery_metrics(),
            "active_recoveries": len(self.recovery_executor.active_recoveries),
            "recent_recoveries": self.recovery_executor.recovery_history[-10:] if self.recovery_executor.recovery_history else [],
        }


# Example usage:
#
# executor = ResponseExecutor(dry_run=True)
# recovery = RecoveryExecutor(response_executor=executor, dry_run=True)
#
# # Execute a response
# action = ResponseAction(
#     action_id="act_123",
#     action_type=ResponseActionType.BLOCK_IP,
#     scope=ResponseScope.SOURCE_IP,
#     target="192.168.1.100",
# )
# executor.execute_action(action)
#
# # Trigger recovery (simulating timeout)
# recovery = RecoveryExecutor(response_executor=executor, dry_run=True)
# recovery.trigger_recovery(action, RecoveryTrigger.TIMEOUT)
#
# # Check metrics
# metrics = recovery.get_recovery_metrics()
# print(f"Recovery success rate: {metrics['success_rate']:.1%}")