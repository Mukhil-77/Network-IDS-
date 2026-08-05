"""
Action registry (documented path: response_engine/registry.py).

The single place every response action is registered and looked up by name.
The implementation lives in backend/response_engine/response_registry.py;
this module is the documented entry point and re-exports the full public
API so both import paths work identically.
"""

from backend.response_engine.response_registry import (
    ActionResult,
    ResponseContext,
    ensure_actions_loaded,
    get_handler,
    get_rollback_action,
    list_actions,
    register_action,
)

__all__ = [
    "ActionResult",
    "ResponseContext",
    "ensure_actions_loaded",
    "get_handler",
    "get_rollback_action",
    "list_actions",
    "register_action",
]
