"""
Action execution engine (documented path: response_engine/executor.py).

Runs an ordered list of action names against one ResponseContext, catching
each action's exceptions so one failing action never prevents the rest of
the policy from running. The implementation lives in
backend/response_engine/response_executor.py; this module is the documented
entry point and re-exports it.
"""

from backend.response_engine.response_executor import execute_actions

__all__ = ["execute_actions"]
