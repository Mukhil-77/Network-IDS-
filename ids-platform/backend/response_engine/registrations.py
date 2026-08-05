"""
Built-in action registrations (documented path: response_engine/registrations.py).

Every built-in action module registers its handlers as a side effect of
being imported (see each module's bottom: firewall.py, quarantine.py,
recovery.py, notifications.py). This module triggers those imports exactly
once per process - the registry's ``_loaded`` guard makes the call
idempotent, so calling ``register_default_actions()`` from anywhere (startup,
tests, a REPL) never double-registers a handler.
"""

from __future__ import annotations

from backend.response_engine.response_registry import ensure_actions_loaded


def register_default_actions() -> None:
    """Import every action module once, triggering their registrations."""
    ensure_actions_loaded()


# Register built-ins at import time so `import backend.response_engine.registrations`
# is enough to have the full 11-action registry populated - matching how
# response_service.py's module-level `ensure_actions_loaded()` behaves.
register_default_actions()

__all__ = ["register_default_actions"]
