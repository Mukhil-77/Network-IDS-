"""
Policy engine: loads severity -> action-list mappings (and the global
simulation_mode flag) from response_rules.yaml, and persists updates back
to it (PUT /response-rules).

A YAML file, not the database, is the source of truth for policy - per the
spec ("Rules must be configurable through JSON/YAML"), and because policy
is operational configuration (like an .env file), not application data;
keeping it out of the database means it can be reviewed/diffed in version
control and doesn't require a migration to change.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Optional

import yaml

from backend.response_engine.response_registry import ensure_actions_loaded, list_actions
from backend.utils.logger import get_logger

logger = get_logger(__name__)

DEFAULT_RULES_PATH = Path(__file__).parent / "config" / "response_rules.yaml"


def _resolve_rules_path() -> Path:
    """
    Desktop-app packaging: the default path lives next to the code (read-only
    in a frozen PyInstaller build), but PUT /response-rules writes it back, so
    the Electron shell points RESPONSE_RULES_PATH at a writable user-data copy.
    Falls back to the packaged default when unset (normal/bundled dev).
    """
    override = os.environ.get("RESPONSE_RULES_PATH")
    if override:
        return Path(override)
    return DEFAULT_RULES_PATH


class InvalidPolicyError(Exception):
    """Raised when a policy update references an action that isn't registered."""


class PolicyEngine:
    def __init__(self, rules_path: Optional[Path] = None):
        self.rules_path = rules_path or _resolve_rules_path()
        self._lock = threading.RLock()
        self._policies: dict[str, list[str]] = {}
        self._simulation_mode: bool = True
        self._load()

    def _load(self) -> None:
        with self._lock:
            if not self.rules_path.is_file():
                logger.warning("Response rules file not found at %s; using empty policy set", self.rules_path)
                self._policies = {}
                self._simulation_mode = True
                return

            with open(self.rules_path) as f:
                data = yaml.safe_load(f) or {}

            self._policies = {str(k): list(v) for k, v in (data.get("policies") or {}).items()}
            self._simulation_mode = bool(data.get("simulation_mode", True))
            logger.info(
                "Loaded response policies for severities: %s (simulation_mode=%s)",
                list(self._policies.keys()), self._simulation_mode,
            )

    def get_actions(self, severity: str) -> list[str]:
        with self._lock:
            actions = self._policies.get(severity)
        if actions is None:
            logger.warning("No response policy configured for severity '%s'; no actions will run", severity)
            return []
        return list(actions)

    def is_simulation_mode(self) -> bool:
        with self._lock:
            return self._simulation_mode

    def get_all_policies(self) -> dict[str, list[str]]:
        with self._lock:
            return {severity: list(actions) for severity, actions in self._policies.items()}

    def update(self, policies: Optional[dict[str, list[str]]] = None, simulation_mode: Optional[bool] = None) -> None:
        """
        Validate and apply an update, then persist to `rules_path`.

        Raises:
            InvalidPolicyError: If any action name in `policies` isn't registered.
        """
        ensure_actions_loaded()
        known_actions = set(list_actions())

        if policies is not None:
            for severity, actions in policies.items():
                unknown = [a for a in actions if a not in known_actions]
                if unknown:
                    raise InvalidPolicyError(
                        f"Unknown action(s) for severity '{severity}': {unknown}. "
                        f"Registered actions: {sorted(known_actions)}"
                    )

        with self._lock:
            if policies is not None:
                self._policies = {k: list(v) for k, v in policies.items()}
            if simulation_mode is not None:
                self._simulation_mode = simulation_mode
            self._write()

        logger.info("Response policies updated (simulation_mode=%s)", self._simulation_mode)

    def _write(self) -> None:
        self.rules_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.rules_path, "w") as f:
            yaml.safe_dump(
                {"simulation_mode": self._simulation_mode, "policies": self._policies},
                f, sort_keys=False,
            )


# Process-wide instance - imported by response_service.py and the API routes.
policy_engine = PolicyEngine()
