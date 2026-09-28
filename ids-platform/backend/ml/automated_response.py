"""
Controlled Automated Response System

Implements a safe, auditable automated response pipeline:
DETECT → SCORE → VERIFY → RESPOND → LOG

Response levels:
- LOW: Log only
- MEDIUM: Create alert + notify
- HIGH: Alert + temporary containment recommendation
- CRITICAL: Alert + configurable automated blocking/isolation

Safety features:
- Requires explicit configuration for destructive actions
- All responses logged with full audit trail
- Rollback capability for temporary blocks
- Dry-run mode for testing
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Optional, Callable
from collections import defaultdict
from threading import Lock

import uuid

from backend.ml.alert_prioritization import Alert, AlertPriority
from backend.ml.risk_scoring import PredictionResult, RiskLevel
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class ResponseAction(Enum):
    """Types of automated responses."""
    LOG_ONLY = "LOG_ONLY"
    CREATE_ALERT = "CREATE_ALERT"
    NOTIFY_SOC = "NOTIFY_SOC"
    QUARANTINE_HOST = "QUARANTINE_HOST"
    BLOCK_IP = "BLOCK_IP"
    RATE_LIMIT = "RATE_LIMIT"
    ISOLATE_NETWORK = "ISOLATE_NETWORK"
    CLOSE_CONNECTION = "CLOSE_CONNECTION"
    QUARANTINE_FILE = "QUARANTINE_FILE"
    ROLLBACK_CHANGES = "ROLLBACK_CHANGES"


class ResponseStatus(Enum):
    """Status of a response action."""
    PENDING = "PENDING"
    VERIFYING = "VERIFYING"
    APPROVED = "APPROVED"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    ROLLED_BACK = "ROLLED_BACK"
    REJECTED = "REJECTED"


@dataclass
class ResponsePolicy:
    """Defines when and how to respond to alerts."""
    name: str
    description: str
    trigger_conditions: dict  # e.g., {"risk_score": ">=", "value": 80, "severity": "CRITICAL"}
    actions: list[ResponseAction]
    requires_approval: bool = True
    auto_execute: bool = False
    rollback_after: Optional[timedelta] = None
    dry_run: bool = False
    enabled: bool = True


@dataclass
class ResponseActionRecord:
    """Record of a single response action execution."""
    action_id: str
    response_id: str
    action: ResponseAction
    target: str  # IP, host, file, etc.
    parameters: dict
    status: ResponseStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    result: Optional[dict] = None
    error: Optional[str] = None
    rollback_info: Optional[dict] = None
    
    def to_dict(self) -> dict:
        return {
            "action_id": self.action_id,
            "response_id": self.response_id,
            "action": self.action.value,
            "target": self.target,
            "parameters": self.parameters,
            "status": self.status.value,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "result": self.result,
            "error": self.error,
            "rollback_info": self.rollback_info,
        }


@dataclass
class Response:
    """A complete response to an alert/incident."""
    response_id: str
    alert_id: str
    incident_id: Optional[str]
    policy_name: str
    trigger_alert: 'Alert'
    status: ResponseStatus
    created_at: datetime
    actions: list[ResponseActionRecord] = field(default_factory=list)
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    rollback_available: bool = False
    rollback_deadline: Optional[datetime] = None
    dry_run: bool = False
    
    def to_dict(self) -> dict:
        return {
            "response_id": self.response_id,
            "alert_id": self.alert_id,
            "incident_id": self.incident_id,
            "policy_name": self.policy_name,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "actions": [a.to_dict() for a in self.actions],
            "approved_by": self.approved_by,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "rollback_available": self.rollback_available,
            "rollback_deadline": self.rollback_deadline.isoformat() if self.rollback_deadline else None,
            "dry_run": self.dry_run,
        }


# Pre-defined response policies
DEFAULT_POLICIES = [
    ResponsePolicy(
        name="low_risk_log_only",
        description="Log low-risk alerts for audit trail",
        trigger_conditions={"risk_score": "<=", "value": 20},
        actions=[ResponseAction.LOG_ONLY],
        requires_approval=False,
        auto_execute=True,
    ),
    ResponsePolicy(
        name="medium_risk_alert_notify",
        description="Create alert and notify SOC for medium risk",
        trigger_conditions={"risk_score": ">=", "value": 40, "risk_score_max": 60},
        actions=[ResponseAction.CREATE_ALERT, ResponseAction.NOTIFY_SOC],
        requires_approval=False,
        auto_execute=True,
    ),
    ResponsePolicy(
        name="high_risk_containment",
        description="Alert + temporary containment for high risk",
        trigger_conditions={"risk_score": ">=", "value": 60, "risk_score_max": 80},
        actions=[ResponseAction.CREATE_ALERT, ResponseAction.NOTIFY_SOC, ResponseAction.RATE_LIMIT],
        requires_approval=True,
        auto_execute=False,
        rollback_after=timedelta(hours=24),
    ),
    ResponsePolicy(
        name="critical_auto_block",
        description="Auto-block for critical threats (if enabled)",
        trigger_conditions={"risk_score": ">=", "value": 80},
        actions=[
            ResponseAction.CREATE_ALERT, 
            ResponseAction.NOTIFY_SOC, 
            ResponseAction.BLOCK_IP,
            ResponseAction.RATE_LIMIT
        ],
        requires_approval=True,
        auto_execute=False,
        rollback_after=timedelta(hours=1),
    ),
]


class ResponseExecutor:
    """
    Executes response actions safely with logging and rollback support.
    """
    
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self._lock = Lock()
        self._action_handlers: dict[ResponseAction, Callable] = {
            ResponseAction.LOG_ONLY: self._log_only,
            ResponseAction.CREATE_ALERT: self._create_alert,
            ResponseAction.NOTIFY_SOC: self._notify_soc,
            ResponseAction.QUARANTINE_HOST: self._quarantine_host,
            ResponseAction.BLOCK_IP: self._block_ip,
            ResponseAction.RATE_LIMIT: self._rate_limit,
            ResponseAction.ISOLATE_NETWORK: self._isolate_network,
            ResponseAction.CLOSE_CONNECTION: self._close_connection,
            ResponseAction.QUARANTINE_FILE: self._quarantine_file,
        }
    
    def execute(
        self,
        action: ResponseAction,
        target: str,
        parameters: dict = None,
        rollback_after: timedelta = None,
    ) -> ResponseActionRecord:
        """Execute a response action."""
        action_id = str(uuid.uuid4())[:8]
        record = ResponseActionRecord(
            action_id=action_id,
            response_id="",  # Will be set by ResponseEngine
            action=action,
            target=target,
            parameters=parameters or {},
            status=ResponseStatus.PENDING,
            started_at=datetime.now(timezone.utc),
        )
        
        handler = self._action_handlers.get(action)
        if not handler:
            record.status = ResponseStatus.FAILED
            record.error = f"No handler for action: {action}"
            return record
        
        record.status = ResponseStatus.EXECUTING
        
        try:
            if self.dry_run:
                # Dry run - simulate execution
                result = {"dry_run": True, "message": f"Would execute {action.value} on {target}"}
                record.status = ResponseStatus.COMPLETED
                record.result = result
                logger.info(f"[DRY RUN] {action.value} on {target}: {result}")
            else:
                # Actual execution
                result = handler(target, parameters or {})
                record.status = ResponseStatus.COMPLETED
                record.result = result
                logger.info(f"Executed {action.value} on {target}: {result}")
                
        except Exception as e:
            record.status = ResponseStatus.FAILED
            record.error = str(e)
            logger.error(f"Failed to execute {action.value} on {target}: {e}")
        
        record.completed_at = datetime.now(timezone.utc)
        return record
    
    # Action handlers
    def _log_only(self, target: str, params: dict) -> dict:
        """Log the event."""
        return {"logged": True, "target": target, "message": f"Logged event for {target}"}
    
    def _create_alert(self, target: str, params: dict) -> dict:
        """Create an alert in the system."""
        return {"alert_created": True, "target": target, "alert_id": f"ALT-{uuid.uuid4().hex[:8]}"}
    
    def _notify_soc(self, target: str, params: dict) -> dict:
        """Send notification to SOC."""
        return {"notified": True, "target": target, "channels": ["email", "slack", "pagerduty"]}
    
    def _quarantine_host(self, target: str, params: dict) -> dict:
        """Quarantine a host (simulate)."""
        duration = params.get("duration_minutes", 60)
        return {
            "quarantined": True, 
            "target": target, 
            "duration_minutes": duration,
            "quarantine_id": f"Q-{uuid.uuid4().hex[:8]}",
            "rollback_at": (datetime.now(timezone.utc) + timedelta(minutes=params.get("duration_minutes", 60))).isoformat(),
        }
    
    def _block_ip(self, target: str, params: dict) -> dict:
        """Block an IP address (simulate)."""
        duration = params.get("duration_minutes", 60)
        return {
            "blocked": True,
            "target": target,
            "duration_minutes": duration,
            "block_id": f"B-{uuid.uuid4().hex[:8]}",
            "rollback_at": (datetime.now(timezone.utc) + timedelta(minutes=params.get("duration_minutes", 60))).isoformat(),
        }
    
    def _rate_limit(self, target: str, params: dict) -> dict:
        """Apply rate limiting to an IP."""
        rate = params.get("requests_per_minute", 10)
        return {
            "rate_limited": True,
            "target": target,
            "requests_per_minute": rate,
            "limit_id": f"RL-{uuid.uuid4().hex[:8]}",
        }
    
    def _isolate_network(self, target: str, params: dict) -> dict:
        """Isolate a network segment."""
        return {
            "isolated": True,
            "target": target,
            "isolation_id": f"ISO-{uuid.uuid4().hex[:8]}",
        }
    
    def _close_connection(self, target: str, params: dict) -> dict:
        """Close a network connection."""
        return {"closed": True, "target": target}
    
    def _quarantine_file(self, target: str, params: dict) -> dict:
        """Quarantine a suspicious file."""
        return {
            "quarantined": True,
            "target": target,
            "quarantine_id": f"FQ-{uuid.uuid4().hex[:8]}",
        }


class ResponseEngine:
    """
    Main response engine that coordinates the DETECT→SCORE→VERIFY→RESPOND→LOG pipeline.
    """
    
    def __init__(
        self,
        policies: list[ResponsePolicy] = None,
        dry_run: bool = True,
        require_approval_for: list[ResponseAction] = None,
    ):
        self.policies = policies or DEFAULT_POLICIES
        self.dry_run = dry_run
        self.require_approval_for = require_approval_for or [
            ResponseAction.BLOCK_IP,
            ResponseAction.QUARANTINE_HOST,
            ResponseAction.ISOLATE_NETWORK,
        ]
        
        self.executor = ResponseExecutor(dry_run=dry_run)
        self.responses: dict[str, Response] = {}
        self._lock = Lock()
        
        # Audit log
        self.audit_log: list[dict] = []
    
    def process_alert(self, alert: Alert, incident_id: str = None) -> Optional[Response]:
        """
        Process an alert through the response pipeline.
        
        Pipeline: DETECT → SCORE → VERIFY → RESPOND → LOG
        """
        # DETECT: Alert already detected
        # SCORE: Alert already scored
        
        # VERIFY: Match against policies
        matching_policies = self._match_policies(alert)
        
        if not matching_policies:
            logger.info(f"No matching policies for alert {alert.alert_id}")
            return None
        
        # Use highest priority matching policy
        policy = max(matching_policies, key=lambda p: self._policy_priority(p))
        
        # VERIFY: Check if approval needed
        needs_approval = any(a in self.require_approval_for for a in policy.actions)
        
        # Create response record
        response_id = f"RESP-{uuid.uuid4().hex[:8]}"
        response = Response(
            response_id=response_id,
            alert_id=alert.alert_id,
            incident_id=incident_id,
            policy_name=policy.name,
            trigger_alert=alert,
            status=ResponseStatus.PENDING if not policy.auto_execute else ResponseStatus.VERIFYING,
            created_at=datetime.now(timezone.utc),
            dry_run=self.dry_run,
        )
        
        if policy.rollback_after:
            response.rollback_available = True
            response.rollback_deadline = datetime.now(timezone.utc) + policy.rollback_after
        
        # Execute actions
        if policy.auto_execute and not needs_approval:
            response.status = ResponseStatus.EXECUTING
            self._execute_actions(response, policy)
            response.status = ResponseStatus.COMPLETED
            response.completed_at = datetime.now(timezone.utc)
        elif needs_approval:
            response.status = ResponseStatus.VERIFYING
            # Would wait for approval in real implementation
        else:
            response.status = ResponseStatus.COMPLETED
        
        with Lock():
            self.responses[response_id] = response
            self._log_audit(response)
        
        return response
    
    def _match_policies(self, alert: Alert) -> list[ResponsePolicy]:
        """Find policies matching the alert."""
        matches = []
        for policy in self.policies:
            if not policy.enabled:
                continue
            
            if self._matches_conditions(alert, policy.trigger_conditions):
                matches.append(policy)
        
        return matches
    
    def _matches_conditions(self, alert: Alert, conditions: dict) -> bool:
        """Check if alert matches policy conditions.
        
        Expected condition formats:
        - risk_score: {"<=": 20} or {">=": 80} or {">=": 80, "<=": 60}
        - risk_score_max: 60
        - severity: ["CRITICAL", "HIGH"] or "CRITICAL"
        - attack_type: ["DDoS", "DoS"] or "DDoS"
        """
        # Handle risk_score conditions (can be multiple operators)
        if "risk_score" in conditions:
            rs_cond = conditions["risk_score"]
            if isinstance(rs_cond, dict):
                for op, value in rs_cond.items():
                    if op == ">=" and alert.risk_score < value:
                        return False
                    elif op == "<=" and alert.risk_score > value:
                        return False
        
        # Handle risk_score_max
        if "risk_score_max" in conditions:
            value = conditions["risk_score_max"]
            if isinstance(value, dict):
                value = value.get("value", 100)
            if alert.risk_score > value:
                return False
        
        # Handle severity
        if "severity" in conditions:
            sev_cond = conditions["severity"]
            values = sev_cond.get("values", []) if isinstance(sev_cond, dict) else (sev_cond if isinstance(sev_cond, list) else [sev_cond])
            if alert.severity not in values:
                return False
        
        # Handle attack_type
        if "attack_type" in conditions:
            at_cond = conditions["attack_type"]
            values = at_cond.get("values", []) if isinstance(at_cond, dict) else (at_cond if isinstance(at_cond, list) else [at_cond])
            if alert.attack_type not in values:
                return False
        
        return True
    
    def _policy_priority(self, policy: ResponsePolicy) -> int:
        """Get policy priority for ordering."""
        priority_map = {
            "critical_auto_block": 100,
            "high_risk_containment": 80,
            "medium_risk_alert_notify": 60,
            "low_risk_log_only": 40,
        }
        return priority_map.get(policy.name, 50)
    
    def _execute_actions(self, response: Response, policy: ResponsePolicy):
        """Execute all actions in a policy."""
        for action in policy.actions:
            # Determine target from alert
            target = response.trigger_alert.source_ip
            params = {"duration_minutes": 60} if action in [ResponseAction.QUARANTINE_HOST, ResponseAction.BLOCK_IP] else {}
            
            record = self._execute_single_action(response.response_id, action, response.trigger_alert.source_ip, {})
            response.actions.append(record)
    
    def _execute_single_action(self, response_id: str, action: ResponseAction, target: str, params: dict) -> ResponseActionRecord:
        """Execute a single action and record it."""
        record = self.executor.execute(action, target, params)
        record.response_id = response_id
        
        # Log to audit
        self._log_audit({
            "type": "ACTION_EXECUTED",
            "response_id": response_id,
            "action": action.value,
            "target": target,
            "status": record.status.value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        
        return record
    
    def _log_audit(self, entry: dict):
        """Log to audit trail."""
        if hasattr(entry, 'to_dict'):
            entry = entry.to_dict()
        self.audit_log.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **entry,
        })
        if len(self.audit_log) > 10000:
            self.audit_log = self.audit_log[-10000:]
    
    def approve_response(self, response_id: str, approver: str) -> bool:
        """Approve a pending response."""
        with Lock():
            response = self.responses.get(response_id)
            if not response or response.status != ResponseStatus.VERIFYING:
                return False
            
            response.status = ResponseStatus.APPROVED
            response.approved_by = approver
            response.approved_at = datetime.now(timezone.utc)
            response.status = ResponseStatus.EXECUTING
            
            # Execute actions
            policy = next((p for p in self.policies if p.name == response.policy_name), None)
            if policy:
                self._execute_actions(response, policy)
                response.status = ResponseStatus.COMPLETED
                response.completed_at = datetime.now(timezone.utc)
            
            self._log_audit({
                "type": "RESPONSE_APPROVED",
                "response_id": response_id,
                "approver": approver,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            return True
    
    def reject_response(self, response_id: str, reason: str) -> bool:
        """Reject a pending response."""
        with Lock():
            response = self.responses.get(response_id)
            if not response or response.status != ResponseStatus.VERIFYING:
                return False
            
            response.status = ResponseStatus.REJECTED
            self._log_audit({
                "type": "RESPONSE_REJECTED",
                "response_id": response_id,
                "reason": reason,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            return True
    
    def rollback_response(self, response_id: str) -> bool:
        """Rollback a completed response (if rollback available)."""
        with Lock():
            response = self.responses.get(response_id)
            if not response or not response.rollback_available:
                return False
            
            if datetime.now(timezone.utc) > (response.rollback_deadline or datetime.max.replace(tzinfo=timezone.utc)):
                return False
            
            # Rollback each action
            for action_record in response.actions:
                if action_record.status == ResponseStatus.COMPLETED:
                    # Execute rollback based on action type
                    self._rollback_action(action_record)
                    action_record.status = ResponseStatus.ROLLED_BACK
            
            response.rollback_available = False
            self._log_audit({
                "type": "RESPONSE_ROLLED_BACK",
                "response_id": response_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            return True
    
    def _rollback_action(self, action_record: ResponseActionRecord):
        """Rollback a specific action."""
        # Implementation would depend on action type
        # For now, just log
        logger.info(f"Rolling back action {action_record.action_id}: {action_record.action.value} on {action_record.target}")


# Global response engine instance
response_engine = ResponseEngine(dry_run=True)  # Default to dry-run for safety


if __name__ == "__main__":
    print("Automated response module loaded successfully")