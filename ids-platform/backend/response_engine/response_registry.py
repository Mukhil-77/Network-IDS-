"""
Action registry: the single place every response action is registered and
looked up by name. This is what makes the engine "modular and extensible"
per the spec - adding a new action means writing one handler function and
calling `register_action()`, nothing else in this package needs to change.

Handler contract:
    def my_action(context: ResponseContext) -> ActionResult

`register_default_actions()` imports every action module (firewall,
quarantine, recovery, notifications) exactly once, so this stays
idempotent no matter how many times response_service.py or a test imports
it. Each of those modules registers its own handlers as a side effect of
being imported - see e.g. firewall.py's bottom.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass
class ResponseContext:
    """Everything a handler needs to act on one alert. No DB session - handlers are pure w.r.t. persistence, response_history.py does all writing."""

    alert_id: str
    severity: str
    attack_type: str
    source_ip: str
    destination_ip: str
    flow_id: Optional[str]
    mode: str  # "simulation" or "live"
    operator: str = "automated"


@dataclass
class ActionResult:
    action: str
    status: str  # "success" | "failed" | "skipped"
    message: str = ""
    rollback_available: bool = False
    execution_time_ms: float = 0.0
    metadata: dict = field(default_factory=dict)


ActionHandler = Callable[[ResponseContext], ActionResult]

_registry: dict[str, ActionHandler] = {}
_rollback_map: dict[str, str] = {}  # action name -> its rollback action's name
_loaded = False


def register_action(name: str, handler: ActionHandler, rollback_of: Optional[str] = None) -> None:
    """
    Register `handler` under `name`. If this action is itself the rollback
    of another action (e.g. `unblock_ip` rolling back `block_ip`), pass
    `rollback_of` so `get_rollback_action()` can find it.
    """
    _registry[name] = handler
    if rollback_of is not None:
        _rollback_map[rollback_of] = name


def get_handler(name: str) -> Optional[ActionHandler]:
    ensure_actions_loaded()
    return _registry.get(name)


def get_rollback_action(name: str) -> Optional[str]:
    ensure_actions_loaded()
    return _rollback_map.get(name)


def list_actions() -> list[str]:
    ensure_actions_loaded()
    return sorted(_registry.keys())


def ensure_actions_loaded() -> None:
    """Import every action module once, triggering their registrations. Safe to call repeatedly."""
    global _loaded
    if _loaded:
        return
    from backend.response_engine import firewall, notifications, quarantine, recovery  # noqa: F401

    _loaded = True
