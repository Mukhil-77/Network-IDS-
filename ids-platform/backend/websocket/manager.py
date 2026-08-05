"""
Backward-compatible alias of backend/websocket/ws_manager.py.

The canonical implementation (ConnectionManager + connection_manager
singleton) lives in ws_manager.py - the documented module name. This module
exists so existing imports of ``backend.websocket.manager`` (routes/websocket.py,
broadcaster.py, tests) keep working unchanged; it re-exports everything.
"""

from backend.websocket.ws_manager import (
    DEFAULT_CHANNEL,
    HEARTBEAT_INTERVAL_SECONDS,
    ConnectionManager,
    connection_manager,
)

__all__ = ["DEFAULT_CHANNEL", "HEARTBEAT_INTERVAL_SECONDS", "ConnectionManager", "connection_manager"]
