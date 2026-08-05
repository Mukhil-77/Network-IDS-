"""
Severity-based response rule evaluation (documented path: response_engine/rules.py).

Loads default_rules.yaml (backend/response_engine/config/response_rules.yaml),
matches alert severity to configured action lists, and exposes the
simulation-mode flag. The implementation lives in
backend/response_engine/response_rules.py (PolicyEngine + policy_engine
singleton); this module is the documented entry point and re-exports it.
"""

from backend.response_engine.response_rules import (
    DEFAULT_RULES_PATH,
    InvalidPolicyError,
    PolicyEngine,
    policy_engine,
)

__all__ = ["DEFAULT_RULES_PATH", "InvalidPolicyError", "PolicyEngine", "policy_engine"]
