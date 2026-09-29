"""
Automated response engine with risk-gated actions and verification.

Implements DETECT → SCORE → VERIFY → RESPOND → LOG → RECOVER lifecycle
with safety gates and verification.

Research contribution: Verified closed-loop automated response and recovery.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set
from collections import defaultdict
import uuid

from backend.ml.risk_scoring import RiskTier, RiskScorer, AlertContext
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class ResponseActionType(Enum):
    """Types of automated response actions."""
    LOG_ONLY = "log_only"
    ALERT_ANALYST = "alert_analyst"
    RATE_LIMIT = "rate_limit"
    BLOCK_IP = "block_ip"
    QUARANTINE_HOST = "quarantine_host"
    KILL_PROCESS = "kill_process"
    RESTART_SERVICE = "restart_service"
    INCREASE_MONITORING = "increase_monitoring"
    CAPTURE_PACKETS = "capture_packets"
    RUN_FORENSICS = "run_forensics"


class ResponseStatus(Enum):
    """Status of a response action."""
    PENDING = "pending"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    VERIFIED = "verified"
    VERIFICATION_FAILED = "verification_failed"


class ResponseScope(Enum):
    """Scope of response action."""
    SOURCE_IP = "source_ip"
    DESTINATION_IP = "destination_ip"
    SOURCE_HOST = "source_host"
    DESTINATION_HOST = "destination_host"
    NETWORK_SEGMENT = "network_segment"
    APPLICATION = "application"


@dataclass
class ResponseAction:
    """Definition of a response action."""
    action_id: str
    action_type: ResponseActionType
    scope: ResponseScope
    target: str  # IP, host, network segment, etc.
    parameters: Dict[str, Any] = field(default_factory=dict)
    requires_approval: bool = False
    is_reversible: bool = True
    rollback_action: Optional[str] = None  # Action ID to rollback to
    max_duration_minutes: Optional[int] = None  # Auto-expire after this time
    
    # Execution tracking
    status: ResponseStatus = ResponseStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    
    # Verification
    verification_checks: List[Dict] = field(default_factory=list)
    verification_result: Optional[bool] = None
    verified_at: Optional[datetime] = None
    
    # Context
    alert_id: Optional[str] = None
    risk_score: float = 0.0
    risk_tier: str = ""
    triggered_by: str = "automated"  # "automated" or "analyst"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_id": self.action_id,
            "action_type": self.action_type.value,
            "scope": self.scope.value,
            "target": self.target,
            "parameters": self.parameters,
            "requires_approval": self.requires_approval,
            "is_reversible": self.is_reversible,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error_message": self.error_message,
            "verification_result": self.verification_result,
            "alert_id": self.alert_id,
            "risk_score": self.risk_score,
            "risk_tier": self.risk_tier,
        }


@dataclass
class ResponsePolicy:
    """Policy mapping risk tiers to response actions."""
    tier: str  # CRITICAL, HIGH, MEDIUM, GUARDED, LOW
    actions: List[ResponseActionType]
    requires_approval: bool = False
    auto_execute: bool = True
    max_concurrent_actions: int = 3
    cooldown_minutes: int = 5  # Min time between same actions on same target
    
    # Verification settings
    verify_containment: bool = True
    verification_timeout_minutes: int = 5
    auto_rollback_on_failure: bool = True


# Default response policies (can be configured)
DEFAULT_RESPONSE_POLICIES = {
    "CRITICAL": ResponsePolicy(
        tier="CRITICAL",
        actions=[
            ResponseActionType.BLOCK_IP,
            ResponseActionType.ALERT_ANALYST,
            ResponseActionType.INCREASE_MONITORING,
            ResponseActionType.CAPTURE_PACKETS,
        ],
        requires_approval=False,
        auto_execute=True,
        verify_containment=True,
        verification_timeout_minutes=2,
    ),
    "HIGH": ResponsePolicy(
        tier="HIGH",
        actions=[
            ResponseActionType.RATE_LIMIT,
            ResponseActionType.ALERT_ANALYST,
            ResponseActionType.INCREASE_MONITORING,
            ResponseActionType.CAPTURE_PACKETS,
        ],
        requires_approval=False,
        auto_execute=True,
        verify_containment=True,
        verification_timeout_minutes=5,
    ),
    "MEDIUM": ResponsePolicy(
        tier="MEDIUM",
        actions=[
            ResponseActionType.ALERT_ANALYST,
            ResponseActionType.INCREASE_MONITORING,
        ],
        requires_approval=False,
        auto_execute=True,
        verify_containment=False,
    ),
    "GUARDED": ResponsePolicy(
        tier="GUARDED",
        actions=[
            ResponseActionType.LOG_ONLY,
            ResponseActionType.INCREASE_MONITORING,
        ],
        auto_execute=True,
    ),
    "LOW": ResponsePolicy(
        tier="LOW",
        actions=[
            ResponseActionType.LOG_ONLY,
        ],
        auto_execute=True,
    ),
}


@dataclass
class ResponseExecutionResult:
    """Result of executing a response action."""
    action_id: str
    success: bool
    output: str
    error: Optional[str] = None
    verification_result: Optional[bool] = None
    verification_details: Optional[str] = None
    rollback_performed: bool = False
    rollback_error: Optional[str] = None


class ResponseExecutor:
    """
    Executes response actions with verification and rollback support.
    
    This is the core execution engine - replace the action implementations
    with actual infrastructure integrations (firewall APIs, EDR, NAC, etc.)
    """
    
    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run
        self.action_history: List[ResponseAction] = []
        self.active_actions: Dict[str, ResponseAction] = {}
        self.execution_callbacks: Dict[ResponseActionType, Callable] = {}
        self.verification_callbacks: Dict[ResponseActionType, Callable] = {}
        self.rollback_callbacks: Dict[ResponseActionType, Callable] = {}
        
        # Register default handlers (override in production)
        self._register_default_handlers()
    
    def _register_default_handlers(self):
        """Register default action handlers (simulation mode)."""
        self.execution_callbacks = {
            ResponseActionType.LOG_ONLY: self._exec_log_only,
            ResponseActionType.ALERT_ANALYST: self._exec_alert_analyst,
            ResponseActionType.RATE_LIMIT: self._exec_rate_limit,
            ResponseActionType.BLOCK_IP: self._exec_block_ip,
            ResponseActionType.QUARANTINE_HOST: self._exec_quarantine_host,
            ResponseActionType.KILL_PROCESS: self._exec_kill_process,
            ResponseActionType.RESTART_SERVICE: self._exec_restart_service,
            ResponseActionType.INCREASE_MONITORING: self._exec_increase_monitoring,
            ResponseActionType.CAPTURE_PACKETS: self._exec_capture_packets,
            ResponseActionType.RUN_FORENSICS: self._exec_run_forensics,
        }
        
        self.verification_callbacks = {
            ResponseActionType.BLOCK_IP: self._verify_block_ip,
            ResponseActionType.RATE_LIMIT: self._verify_rate_limit,
            ResponseActionType.QUARANTINE_HOST: self._verify_quarantine,
        }
        
        self.rollback_callbacks = {
            ResponseActionType.BLOCK_IP: self._rollback_block_ip,
            ResponseActionType.RATE_LIMIT: self._rollback_rate_limit,
            ResponseActionType.QUARANTINE_HOST: self._rollback_quarantine,
        }
    
    # Execution handlers (replace with real implementations)
    def _exec_log_only(self, action: ResponseAction) -> ResponseExecutionResult:
        logger.info(f"LOG_ONLY: {action.target} - {action.parameters}")
        return ResponseExecutionResult(action.action_id, True, "Logged")
    
    def _exec_alert_analyst(self, action: ResponseAction) -> ResponseExecutionResult:
        logger.warning(f"ALERT_ANALYST: {action.target} - Risk: {action.risk_score}")
        return ResponseExecutionResult(action.action_id, True, "Analyst alerted")
    
    def _exec_rate_limit(self, action: ResponseAction) -> ResponseExecutionResult:
        rate = action.parameters.get("rate_limit_kbps", 1000)
        logger.warning(f"RATE_LIMIT: {action.target} to {rate} kbps (dry_run={self.dry_run})")
        if not self.dry_run:
            # TODO: Implement actual rate limiting (e.g., tc, firewall rules)
            pass
        return ResponseExecutionResult(action.action_id, True, f"Rate limited to {rate} kbps")
    
    def _exec_block_ip(self, action: ResponseAction) -> ResponseExecutionResult:
        duration = action.parameters.get("duration_minutes", 60)
        logger.critical(f"BLOCK_IP: {action.target} for {duration} min (dry_run={self.dry_run})")
        if not self.dry_run:
            # TODO: Implement actual IP blocking (firewall, NAC, etc.)
            pass
        return ResponseExecutionResult(action.action_id, True, f"IP blocked for {duration} min")
    
    def _exec_quarantine_host(self, action: ResponseAction) -> ResponseExecutionResult:
        logger.critical(f"QUARANTINE_HOST: {action.target} (dry_run={self.dry_run})")
        if not self.dry_run:
            # TODO: Implement VLAN isolation, NAC quarantine
            pass
        return ResponseExecutionResult(action.action_id, True, "Host quarantined")
    
    def _exec_kill_process(self, action: ResponseAction) -> ResponseExecutionResult:
        pid = action.parameters.get("pid", "unknown")
        logger.warning(f"KILL_PROCESS: PID {pid} on {action.target} (dry_run={self.dry_run})")
        return ResponseExecutionResult(action.action_id, True, f"Process {pid} terminated")
    
    def _exec_restart_service(self, action: ResponseAction) -> ResponseExecutionResult:
        service = action.parameters.get("service", "unknown")
        logger.warning(f"RESTART_SERVICE: {service} on {action.target} (dry_run={self.dry_run})")
        return ResponseExecutionResult(action.action_id, True, f"Service {service} restarted")
    
    def _exec_increase_monitoring(self, action: ResponseAction) -> ResponseExecutionResult:
        level = action.parameters.get("level", "enhanced")
        logger.info(f"INCREASE_MONITORING: {action.target} to {level} level")
        return ResponseExecutionResult(action.action_id, True, f"Monitoring increased to {level}")
    
    def _exec_capture_packets(self, action: ResponseAction) -> ResponseExecutionResult:
        duration = action.parameters.get("duration_seconds", 300)
        logger.info(f"CAPTURE_PACKETS: {action.target} for {duration}s")
        return ResponseExecutionResult(action.action_id, True, f"Packet capture started for {duration}s")
    
    def _exec_run_forensics(self, action: ResponseAction) -> ResponseExecutionResult:
        logger.info(f"RUN_FORENSICS: {action.target}")
        return ResponseExecutionResult(action.action_id, True, "Forensic collection initiated")
    
    # Verification handlers
    def _verify_block_ip(self, action: ResponseAction) -> Tuple[bool, str]:
        # In real implementation: check firewall rules, test connectivity
        return True, "IP block verified in firewall"
    
    def _verify_rate_limit(self, action: ResponseAction) -> Tuple[bool, str]:
        return True, "Rate limit verified"
    
    def _verify_quarantine(self, action: ResponseAction) -> Tuple[bool, str]:
        return True, "Host quarantine verified"
    
    # Rollback handlers
    def _rollback_block_ip(self, action: ResponseAction) -> Tuple[bool, str]:
        logger.info(f"ROLLBACK: Unblocking IP {action.target}")
        return True, "IP unblocked"
    
    def _rollback_rate_limit(self, action: ResponseAction) -> Tuple[bool, str]:
        return True, "Rate limit removed"
    
    def _rollback_quarantine(self, action: ResponseAction) -> Tuple[bool, str]:
        return True, "Host released from quarantine"
    
    def execute_action(self, action: ResponseAction) -> ResponseExecutionResult:
        """Execute a response action with verification."""
        action.status = ResponseStatus.EXECUTING
        action.started_at = datetime.now()
        self.active_actions[action.action_id] = action
        
        # Execute
        handler = self.execution_callbacks.get(action.action_type)
        if not handler:
            result = ResponseExecutionResult(
                action.action_id, False, "", 
                f"No handler for action type: {action.action_type}"
            )
        else:
            try:
                result = handler(action)
            except Exception as e:
                logger.exception(f"Action execution failed: {e}")
                result = ResponseExecutionResult(action.action_id, False, "", str(e))
        
        action.status = ResponseStatus.COMPLETED if result.success else ResponseStatus.FAILED
        action.completed_at = datetime.now()
        action.error_message = result.error
        
        # Verify if required
        if result.success and action.action_type in self.verification_callbacks:
            verify_handler = self.verification_callbacks[action.action_type]
            verified, details = verify_handler(action)
            action.verification_result = verified
            action.verified_at = datetime.now()
            result.verification_result = verified
            result.verification_details = details
            
            if not verified and action.action_type in self.rollback_callbacks:
                # Auto-rollback on verification failure
                rollback_handler = self.rollback_callbacks[action.action_type]
                rollback_success, rollback_msg = rollback_handler(action)
                action.status = ResponseStatus.ROLLED_BACK
                result.rollback_performed = True
                result.rollback_error = None if rollback_success else rollback_msg
        
        self.action_history.append(action)
        return result
    
    def execute_policy(
        self, 
        risk_tier: str, 
        context: Dict[str, Any],
        policy: Optional[ResponsePolicy] = None
    ) -> List[ResponseExecutionResult]:
        """Execute all actions for a risk tier policy."""
        policy = policy or DEFAULT_RESPONSE_POLICIES.get(risk_tier)
        if not policy:
            logger.warning(f"No policy for risk tier: {risk_tier}")
            return []
        
        results = []
        executed = 0
        
        for action_type in policy.actions:
            if executed >= policy.max_concurrent_actions:
                break
            
            # Check cooldown
            if self._check_cooldown(action_type, context.get("target", ""), policy.cooldown_minutes):
                continue
            
            action = ResponseAction(
                action_id=str(uuid.uuid4())[:8],
                action_type=action_type,
                scope=self._infer_scope(action_type),
                target=context.get("target", ""),
                parameters=context.get("parameters", {}),
                alert_id=context.get("alert_id"),
                risk_score=context.get("risk_score", 0),
                risk_tier=risk_tier,
                triggered_by="automated" if policy.auto_execute else "analyst",
            )
            
            if policy.requires_approval and policy.auto_execute:
                action.status = ResponseStatus.PENDING
                # In production: queue for analyst approval
                continue
            
            result = self.execute_action(action)
            results.append(result)
            executed += 1
            
            # Verify if policy requires
            if policy.verify_containment and result.success:
                # Verification handled in execute_action
                pass
        
        return results
    
    def _check_cooldown(self, action_type: ResponseActionType, target: str, cooldown_minutes: int) -> bool:
        """Check if action is in cooldown for target."""
        cutoff = datetime.now() - timedelta(minutes=cooldown_minutes)
        for action in reversed(self.action_history):
            if (action.action_type == action_type and 
                action.target == target and 
                action.created_at > cutoff and
                action.status in (ResponseStatus.COMPLETED, ResponseStatus.VERIFIED)):
                return True
        return False
    
    def _infer_scope(self, action_type: ResponseActionType) -> ResponseScope:
        mapping = {
            ResponseActionType.BLOCK_IP: ResponseScope.SOURCE_IP,
            ResponseActionType.RATE_LIMIT: ResponseScope.SOURCE_IP,
            ResponseActionType.QUARANTINE_HOST: ResponseScope.SOURCE_HOST,
            ResponseActionType.KILL_PROCESS: ResponseScope.SOURCE_HOST,
            ResponseActionType.RESTART_SERVICE: ResponseScope.APPLICATION,
            ResponseActionType.INCREASE_MONITORING: ResponseScope.SOURCE_IP,
        }
        return mapping.get(action_type, ResponseScope.SOURCE_IP)


class ResponseOrchestrator:
    """
    High-level orchestrator for the full DETECT → SCORE → VERIFY → RESPOND → LOG → RECOVER lifecycle.
    """
    
    def __init__(
        self,
        risk_scorer: Any = None,
        executor: Optional[ResponseExecutor] = None,
        policies: Optional[Dict[str, ResponsePolicy]] = None,
    ):
        self.risk_scorer = risk_scorer
        self.executor = executor or ResponseExecutor()
        self.policies = policies or DEFAULT_RESPONSE_POLICIES
        self.response_history: List[Dict] = []
    
    def handle_alert(self, alert: Dict[str, Any]) -> Dict[str, Any]:
        """
        Full alert handling pipeline: DETECT → SCORE → VERIFY → RESPOND → LOG
        
        Returns response summary.
        """
        # DETECT: Alert already detected
        # SCORE: Compute risk score
        if self.risk_scorer:
            context = AlertContext(
                predicted_class=alert.get("attack_type", "UNKNOWN"),
                raw_confidence=alert.get("confidence", 0.0),
                calibrated_confidence=alert.get("calibrated_confidence"),
                feature_coverage_ratio=alert.get("feature_coverage", 1.0),
                source_ip=alert.get("source_ip", ""),
                dest_ip=alert.get("destination_ip", ""),
                source_port=alert.get("source_port", 0),
                dest_port=alert.get("destination_port", 0),
                protocol=alert.get("protocol", ""),
                alert_id=alert.get("id", ""),
            )
            risk_result = self.risk_scorer.compute_risk_score(context)
            risk_tier = risk_result.risk_tier.value
        else:
            risk_tier = alert.get("risk_tier", "MEDIUM")
        
        # VERIFY: Check if action needed (already done in risk scoring)
        # RESPOND: Execute policy
        context = {
            "target": alert.get("source_ip", ""),
            "alert_id": alert.get("id"),
            "risk_score": alert.get("risk_score", 0),
            "parameters": alert.get("response_params", {}),
        }
        
        results = self.executor.execute_policy(risk_tier, context)
        
        # LOG: Record everything
        response_record = {
            "alert_id": alert.get("id"),
            "timestamp": datetime.now().isoformat(),
            "risk_tier": risk_tier,
            "risk_score": alert.get("risk_score", 0),
            "actions": [r.action_id for r in results],
            "results": [r.to_dict() if hasattr(r, 'to_dict') else r.__dict__ for r in results],
        }
        self.response_history.append(response_record)
        
        return {
            "risk_tier": risk_tier,
            "actions_executed": len(results),
            "results": results,
            "record": response_record,
        }
    
    def verify_and_recover(self, action_id: str) -> Dict[str, Any]:
        """Verify a past action and trigger recovery if needed."""
        # Find action in history
        action = None
        for a in self.executor.action_history:
            if a.action_id == action_id:
                action = a
                break
        
        if not action:
            return {"success": False, "error": "Action not found"}
        
        # Re-verify
        if action.action_type in self.executor.verification_callbacks:
            verify_handler = self.executor.verification_callbacks[action.action_type]
            verified, details = verify_handler(action)
            
            if not verified:
                # Trigger rollback
                if action.action_type in self.executor.rollback_callbacks:
                    rollback_handler = self.executor.rollback_callbacks[action.action_type]
                    rollback_success, rollback_msg = rollback_handler(action)
                    return {
                        "success": rollback_success,
                        "verified": False,
                        "rollback_performed": rollback_success,
                        "rollback_message": rollback_msg,
                        "details": details,
                    }
        
        return {
            "success": True,
            "verified": True,
            "details": "Action verified successfully",
        }
    
    def get_response_metrics(self) -> Dict[str, Any]:
        """Get response metrics for dashboard."""
        total = len(self.executor.action_history)
        successful = sum(1 for a in self.executor.action_history if a.status == ResponseStatus.COMPLETED)
        verified = sum(1 for a in self.executor.action_history if a.verification_result is True)
        rolled_back = sum(1 for a in self.executor.action_history if a.status == ResponseStatus.ROLLED_BACK)
        
        return {
            "total_actions": total,
            "successful": successful,
            "success_rate": successful / total if total > 0 else 0,
            "verified": verified,
            "verification_rate": verified / successful if successful > 0 else 0,
            "rolled_back": rolled_back,
            "rollback_rate": rolled_back / total if total > 0 else 0,
        }


# Example usage:
#
# executor = ResponseExecutor(dry_run=True)
# orchestrator = ResponseOrchestrator(risk_scorer=RiskScorer(), executor=executor)
#
# # Handle an alert
# alert = {
#     "id": "alert_123",
#     "attack_type": "DoS",
#     "source_ip": "192.168.1.100",
#     "confidence": 95.0,
#     "risk_score": 85,
#     "risk_tier": "HIGH",
# }
# result = orchestrator.handle_alert(alert)
# print(f"Actions executed: {result['actions_executed']}")
#
# # Check metrics
# metrics = orchestrator.get_response_metrics()
# print(f"Success rate: {metrics['success_rate']:.1%}")