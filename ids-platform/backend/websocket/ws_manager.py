"""
WebSocket connection manager (documented path: websocket/ws_manager.py).

Tracks every currently-connected WebSocket client and broadcasts messages
to them. Adds the full documented feature set on top of a plain connection
set:

    connect() / disconnect() / broadcast() / send_personal()
    per-channel tracking (alerts, packets, statistics)
    heartbeat loop (ping every 15s) that prunes stale connections

One process-wide instance lives at the bottom of this module
(``connection_manager``); backend/api/routes/websocket.py registers and
unregisters connections here, and broadcaster.py is the only other module
that calls broadcast(). backend/websocket/manager.py is a backward-
compatible alias of this module (older imports still work).
"""

from __future__ import annotations

import asyncio
import json
from typing import Optional

from fastapi import WebSocket

from backend.utils.logger import get_logger

logger = get_logger(__name__)

DEFAULT_CHANNEL = "default"
HEARTBEAT_INTERVAL_SECONDS = 15.0


class ConnectionManager:
    def __init__(self, heartbeat_interval: float = HEARTBEAT_INTERVAL_SECONDS):
        self._connections: set[WebSocket] = set()
        self._channels: dict[str, set[WebSocket]] = {}
        self._lock = asyncio.Lock()
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._heartbeat_interval = heartbeat_interval

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    async def connect(self, websocket: WebSocket, channel: str = DEFAULT_CHANNEL) -> None:
        """Accept `websocket` and add it to the global set and to `channel`."""
        await websocket.accept()
        async with self._lock:
            self._connections.add(websocket)
            self._channels.setdefault(channel, set()).add(websocket)
        logger.info("WebSocket client connected (channel=%s, total=%d)", channel, len(self._connections))

    async def disconnect(self, websocket: WebSocket) -> None:
        """Remove `websocket` from every set it is in. Idempotent."""
        async with self._lock:
            self._connections.discard(websocket)
            for members in self._channels.values():
                members.discard(websocket)
        logger.info("WebSocket client disconnected (total=%d)", len(self._connections))

    # ------------------------------------------------------------------
    # Messaging
    # ------------------------------------------------------------------

    async def broadcast(self, message: str, channel: Optional[str] = None) -> None:
        """
        Send `message` to every connected client (or, if `channel` is given,
        only to the clients subscribed to that channel). Dead connections
        are dropped, never retried.
        """
        async with self._lock:
            if channel is None:
                connections = list(self._connections)
            else:
                connections = list(self._channels.get(channel, ()))

        if not connections:
            return

        dead: list[WebSocket] = []
        for connection in connections:
            try:
                await connection.send_text(message)
            except Exception:  # noqa: BLE001 - a broken client must not break the broadcast for everyone else
                dead.append(connection)

        if dead:
            async with self._lock:
                for connection in dead:
                    self._connections.discard(connection)
                    for members in self._channels.values():
                        members.discard(connection)
            logger.info("Dropped %d dead WebSocket connection(s) during broadcast", len(dead))

    async def send_personal(self, message: str, websocket: WebSocket) -> None:
        """Send `message` to a single client."""
        await websocket.send_text(message)

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def connection_count(self) -> int:
        return len(self._connections)

    def channel_size(self, channel: str) -> int:
        return len(self._channels.get(channel, ()))

    # ------------------------------------------------------------------
    # Heartbeat + stale-connection cleanup
    # ------------------------------------------------------------------

    def start_heartbeat(self) -> None:
        """Start the periodic ping loop (idempotent - safe to call repeatedly)."""
        if self._heartbeat_task is not None:
            return
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop(), name="ws-heartbeat")
        logger.info("WebSocket heartbeat started (interval=%.0fs)", self._heartbeat_interval)

    async def stop_heartbeat(self) -> None:
        """Cancel the heartbeat loop, if one is running."""
        if self._heartbeat_task is not None:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
            self._heartbeat_task = None

    async def _heartbeat_loop(self) -> None:
        while True:
            await asyncio.sleep(self._heartbeat_interval)
            await self._ping_all()

    async def _ping_all(self) -> None:
        """Send a JSON ping to every client; silently prune the unreachable."""
        ping = json.dumps({"type": "ping", "payload": {}})
        await self.broadcast(ping)


# Process-wide instance - routes/websocket.py, broadcaster.py and main.py
# all import this (manager.py re-exports it for backward compatibility).
connection_manager = ConnectionManager()
