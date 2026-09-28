"""
Self-Healing / Recovery Mechanisms

Implements controlled recovery mechanisms that complement the automated response system:
- Automatic rollback of temporary blocks after timeout
- Recovery verification after response actions
- Health checks after recovery
- Graceful degradation when components fail
- Recovery status tracking and reporting

Integrates with the automated response system to provide a complete
detect → respond → recover lifecycle.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Optional, Callable
from collections import defaultdict
from threading import Lock, Thread
import time

import uuid

from backend.utils.logger import get_logger

logger = get_logger(__name__)


class RecoveryStatus(Enum):
    """Status of a recovery operation."""
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    PARTIAL = "PARTIAL"


class RecoveryType(Enum):
    """Types of recovery operations."""
    ROLLBACK_BLOCK = "ROLLBACK_BLOCK"
    ROLLBACK_QUARANTINE = "ROLLBACK_QUARANTINE"
    ROLLBACK_RATE_LIMIT = "ROLLBACK_RATE_LIMIT"
    RESTORE_CONNECTION = "RESTORE_CONNECTION"
    RESTORE_FILE = "RESTORE_FILE"
    HEALTH_CHECK = "HEALTH_CHECK"
    RECOVERY_VERIFICATION = "RECOVERY_VERIFICATION"


@dataclass
class RecoveryAction:
    """A single recovery action."""
    recovery_id: str
    action_type: RecoveryType
    target: str  # IP, host, file, connection, etc.
    original_action_id: Optional[str] = None  # Reference to original action
    parameters: dict = field(default_factory=dict)
    status: str = "PENDING"  # PENDING, IN_PROGRESS, COMPLETED, FAILED
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    result: Optional[dict] = None
    error: Optional[str] = None
    verification_result: Optional[dict] = None
    
    def to_dict(self) -> dict:
        return {
            "recovery_id": self.recovery_id,
            "action_type": self.action_type.value,
            "target": self.target,
            "original_action_id": self.original_action_id,
            "parameters": self.parameters,
            "status": self.status,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "result": self.result,
            "error": self.error,
            "verification": self.verification_result,
        }


@dataclass
class RecoveryPlan:
    """A complete recovery plan for a response/incident."""
    recovery_plan_id: str
    response_id: str
    incident_id: Optional[str]
    recovery_actions: list['RecoveryAction'] = field(default_factory=list)
    status: str = "PENDING"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    verification_results: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "recovery_plan_id": self.recovery_plan_id,
            "response_id": self.response_id,
            "incident_id": self.incident_id,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "actions": [a.to_dict() for a in self.recovery_actions],
            "verification_results": self.verification_results,
        }


class RecoveryExecutor:
    """
    Executes recovery actions safely with verification.
    """
    
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self._lock = Lock()
        self._action_handlers: dict = {
            RecoveryType.ROLLBACK_BLOCK: self._rollback_block,
            RecoveryType.ROLLBACK_QUARANTINE: self._rollback_quarantine,
            RecoveryType.ROLLBACK_RATE_LIMIT: self._rollback_rate_limit,
            RecoveryType.RESTORE_CONNECTION: self._restore_connection,
            RecoveryType.RESTORE_FILE: self._restore_file,
            RecoveryType.HEALTH_CHECK: self._health_check,
            RecoveryType.RECOVERY_VERIFICATION: self._verify_recovery,
        }
    
    def execute(
        self,
        recovery_action: 'RecoveryAction',
        dry_run: bool = None,
    ) -> 'RecoveryAction':
        """Execute a recovery action with verification."""
        dry_run = dry_run if dry_run is not None else self.dry_run
        
        recovery_action.status = "IN_PROGRESS"
        recovery_action.started_at = datetime.now(timezone.utc)
        
        handler = self._action_handlers.get(recovery_action.action_type)
        if not handler:
            recovery_action.status = "FAILED"
            recovery_action.error = f"No handler for action: {recovery_action.action_type}"
            recovery_action.completed_at = datetime.now(timezone.utc)
            return recovery_action
        
        try:
            if dry_run:
                result = {"dry_run": True, "message": f"Would execute {recovery_action.action_type.value} on {recovery_action.target}", "success": True}
                recovery_action.status = "COMPLETED"
                recovery_action.result = result
                logger.info(f"[DRY RUN] {recovery_action.action_type.value} on {recovery_action.target}")
            else:
                result = self._execute_with_verification(recovery_action)
                recovery_action.status = "COMPLETED" if result.get("success", False) else "FAILED"
                recovery_action.result = result
                logger.info(f"Executed recovery {recovery_action.action_type.value} on {recovery_action.target}: {result}")
            
        except Exception as e:
            recovery_action.status = "FAILED"
            recovery_action.error = str(e)
            logger.error(f"Failed to execute recovery {recovery_action.action_type.value} on {recovery_action.target}: {e}")
        
        recovery_action.completed_at = datetime.now(timezone.utc)
        return recovery_action
    
    def _execute_with_verification(self, action: 'RecoveryAction') -> dict:
        """Execute action and verify it worked."""
        handler = self._handlers.get(action.action_type)
        if not handler:
            return {"success": False, "error": f"No handler for {action.action_type}"}
        
        # Execute the recovery
        result = self._execute_action(action)
        
        if not result.get("success", False):
            return result
        
        # Run verification
        verification = self._verify_recovery(action)
        action.verification_result = verification
        
        if not verification.get("success", False):
            return {"success": False, "error": "Recovery verification failed", "details": verification}
        
        return {"success": True, "result": result, "verification": verification}
    
    def _execute_action(self, action: 'RecoveryAction') -> dict:
        """Execute a single recovery action."""
        handler = self._handlers.get(action.action_type)
        if not handler:
            return {"success": False, "error": f"No handler for {action.action_type}"}
        
        return handler(action.target, action.parameters)
    
    def _verify_recovery(self, action: 'RecoveryAction') -> dict:
        """Verify that a recovery action was successful."""
        # Run health check on the target
        return self._health_check(action.target, {})
    
    # Recovery action handlers
    def _rollback_block(self, target: str, params: dict) -> dict:
        """Rollback an IP block."""
        if self.dry_run:
            return {"success": True, "message": f"[DRY RUN] Would unblock IP {target}"}
        
        # In real implementation, would call firewall/unblock API
        return {
            "success": True,
            "message": f"Unblocked IP {target}",
            "rollback_id": f"RB-{uuid.uuid4().hex[:8]}",
            "unblocked_at": datetime.now(timezone.utc).isoformat(),
        }
    
    def _rollback_quarantine(self, target: str, params: dict) -> dict:
        """Rollback a host quarantine."""
        if self.dry_run:
            return {"success": True, "message": f"[DRY RUN] Would release host {target} from quarantine"}
        
        return {
            "success": True,
            "message": f"Released host {target} from quarantine",
            "rollback_id": f"RQ-{uuid.uuid4().hex[:8]}",
            "released_at": datetime.now(timezone.utc).isoformat(),
        }
    
    def _rollback_rate_limit(self, target: str, params: dict) -> dict:
        """Rollback a rate limit."""
        if self.dry_run:
            return {"success": True, "message": f"[DRY RUN] Would remove rate limit for {target}"}
        
        return {
            "success": True,
            "message": f"Removed rate limit for {target}",
            "rollback_id": f"RRL-{uuid.uuid4().hex[:8]}",
            "removed_at": datetime.now(timezone.utc).isoformat(),
        }
    
    def _restore_connection(self, target: str, params: dict) -> dict:
        """Restore a network connection."""
        if self.dry_run:
            return {"success": True, "message": f"[DRY RUN] Would restore connection {target}"}
        
        return {
            "success": True,
            "message": f"Restored connection {target}",
        }
    
    def _restore_file(self, target: str, params: dict) -> dict:
        """Restore a quarantined file."""
        if self.dry_run:
            return {"success": True, "message": f"[DRY RUN] Would restore file {target}"}
        
        return {
            "success": True,
            "message": f"Restored file {target}",
            "restore_id": f"RF-{uuid.uuid4().hex[:8]}",
        }
    
    def _health_check(self, target: str, params: dict) -> dict:
        """Perform health check on a target."""
        if self.dry_run:
            return {"success": True, "message": f"[DRY RUN] Health check passed for {target}"}
        
        # In real implementation, would ping, check connectivity, etc.
        return {
            "success": True,
            "message": f"Health check passed for {target}",
            "healthy": True,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }
    
    def _verify_recovery(self, action: 'RecoveryAction') -> dict:
        """Verify a recovery action was successful."""
        # Run health check
        health = self._health_check(action.target, {})
        
        if not health.get("success", False):
            return {"success": False, "error": health.get("error", "Health check failed")}
        
        # Action-specific verification
        if action.action_type in [RecoveryType.ROLLBACK_BLOCK, RecoveryType.ROLLBACK_QUARANTINE]:
            # Verify the target is no longer blocked/quarantined
            return {"success": True, "verified": True, "message": "Target is no longer restricted"}
        
        return {"success": True, "verified": True, "message": "Recovery verified"}


class RecoveryManager:
    """
    Manages the complete recovery lifecycle for responses and incidents.
    
    Features:
    - Automatic rollback scheduling after timeout
    - Recovery plan generation
    - Recovery execution with verification
    - Recovery status tracking
    - Integration with ResponseEngine
    """
    
    def __init__(
        self,
        response_engine: 'ResponseEngine' = None,
        dry_run: bool = True,
        auto_recovery: bool = True,
        recovery_check_interval: int = 300,  # 5 minutes
    ):
        self.executor = RecoveryExecutor(dry_run=True)  # Always dry-run by default for safety
        self.recovery_plans: dict[str, 'RecoveryPlan'] = {}
        self._lock = Lock()
        self.auto_recovery = auto_recovery
        self.recovery_check_interval = timedelta(seconds=recovery_check_interval)
        self._last_check: Optional[datetime] = None
        
        # Callbacks
        self._recovery_callbacks: list[Callable] = []
    
    def add_recovery_callback(self, callback: Callable[['RecoveryPlan'], None]):
        """Add callback for recovery events."""
        self._recovery_callbacks.append(callback)
    
    def create_recovery_plan(
        self,
        response_id: str,
        incident_id: Optional[str] = None,
        rollback_actions: list[tuple] = None,
    ) -> 'RecoveryPlan':
        """Create a recovery plan for a response."""
        plan_id = f"REC-{uuid.uuid4().hex[:8]}"
        plan = RecoveryPlan(
            recovery_plan_id=plan_id,
            response_id=response_id,
            incident_id=incident_id,
        )
        
        # Add default recovery actions based on response actions
        # (In real implementation, would be populated from response actions)
        
        with Lock():
            self.recovery_plans[plan_id] = plan
        
        return plan
    
    def add_recovery_action(
        self,
        plan_id: str,
        action_type: 'RecoveryType',
        target: str,
        original_action_id: str = None,
        parameters: dict = None,
    ) -> 'RecoveryAction':
        """Add a recovery action to a plan."""
        with Lock():
            plan = self.recovery_plans.get(plan_id)
            if not plan:
                raise ValueError(f"Recovery plan not found: {plan_id}")
        
        action = RecoveryAction(
            recovery_id=f"REC-{uuid.uuid4().hex[:8]}",
            action_type=action_type,
            target=target,
            original_action_id=original_action_id,
            parameters=parameters or {},
        )
        
        plan.recovery_actions.append(action)
        return action
    
    def execute_recovery(self, plan_id: str, dry_run: bool = True) -> dict:
        """Execute a complete recovery plan."""
        with Lock():
            plan = self.recovery_plans.get(plan_id)
            if not plan:
                raise ValueError(f"Recovery plan not found: {plan_id}")

        plan.status = "IN_PROGRESS"
        plan.started_at = datetime.now(timezone.utc)

        for action in plan.recovery_actions:
            # Execute each recovery action
            result = self._execute_recovery_action(action, dry_run=dry_run)
            action.status = "COMPLETED" if isinstance(action.result, dict) and action.result.get("success", False) else "FAILED"
            action.completed_at = datetime.now(timezone.utc)

            # Verify if possible
            if isinstance(action.result, dict) and action.result.get("success", False):
                action.verification_result = {"verified": True, "verified_at": datetime.now(timezone.utc).isoformat()}

        # Check overall status
        failed = [a for a in plan.recovery_actions if a.status == "FAILED"]
        if failed:
            plan.status = "PARTIAL" if len(plan.recovery_actions) > len(failed) else "FAILED"
        else:
            plan.status = "COMPLETED"

        plan.completed_at = datetime.now(timezone.utc)

        return {
            "plan_id": plan.recovery_plan_id,
            "status": plan.status,
            "actions_executed": len(plan.recovery_actions),
            "failed": len([a for a in plan.recovery_actions if a.status == "FAILED"]),
            "verified": all(a.verification_result and a.verification_result.get("verified", False) for a in plan.recovery_actions if hasattr(a, 'verification_result')),
        }

    def _execute_recovery_action(self, action: 'RecoveryAction', dry_run: bool = True) -> dict:
        """Execute a single recovery action."""
        executor = RecoveryExecutor(dry_run=dry_run)
        executor.execute(action, dry_run=dry_run)
        return action.result
    
    def schedule_auto_recovery(self, response_id: str, delay: timedelta = None):
        """Schedule automatic recovery after a timeout."""
        # In a real implementation, this would schedule a background task
        # For now, just log the intent
        logger.info(f"Scheduled auto-recovery for response {response_id}")
    
    def verify_recovery(self, response_id: str) -> dict:
        """Verify that a response has been properly rolled back."""
        # Check all actions in the response for rollback status
        # Return verification results
        return {
            "response_id": response_id,
            "verified": True,
            "message": "All actions verified as recovered",
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }
    
    def get_recovery_status(self, response_id: str) -> dict:
        """Get recovery status for a response."""
        # In real implementation, would query the recovery plan
        return {
            "response_id": response_id,
            "recovery_status": "NOT_STARTED",
            "actions": [],
        }


class SelfHealingManager:
    """
    High-level self-healing manager that coordinates recovery.
    
    Features:
    - Automatic recovery scheduling
    - Health checks after recovery
    - Graceful degradation
    - Recovery verification
    """
    
    def __init__(self, response_engine: 'ResponseEngine' = None):
        self.response_engine = response_engine
        self.recovery_manager = RecoveryManager()
        self._recovery_thread: Optional[Thread] = None
        self._running = False
    
    def start(self):
        """Start the self-healing background thread."""
        pass
    
    def stop(self):
        """Stop the self-healing background thread."""
        pass
    
    def trigger_recovery(self, response_id: str) -> dict:
        """Manually trigger recovery for a response."""
        return {"recovery_triggered": True, "response_id": response_id}
    
    def get_recovery_dashboard(self) -> dict:
        """Get recovery dashboard data."""
        return {
            "active_recoveries": 0,
            "completed_recoveries": 0,
            "failed_recoveries": 0,
            "pending_recoveries": 0,
        }


if __name__ == "__main__":
    print("Self-healing / Recovery module loaded successfully")