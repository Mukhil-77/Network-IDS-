"""Unit tests for ConnectionManager, isolated from FastAPI (uses a minimal fake WebSocket)."""

import asyncio

import pytest

from backend.websocket.manager import ConnectionManager


class FakeWebSocket:
    def __init__(self, fail_on_send: bool = False):
        self.accepted = False
        self.sent_messages: list[str] = []
        self.fail_on_send = fail_on_send

    async def accept(self):
        self.accepted = True

    async def send_text(self, message: str):
        if self.fail_on_send:
            raise RuntimeError("connection closed")
        self.sent_messages.append(message)


@pytest.mark.asyncio
async def test_connect_accepts_and_tracks_connection():
    manager = ConnectionManager()
    ws = FakeWebSocket()

    await manager.connect(ws)

    assert ws.accepted
    assert manager.connection_count == 1


@pytest.mark.asyncio
async def test_disconnect_removes_connection():
    manager = ConnectionManager()
    ws = FakeWebSocket()
    await manager.connect(ws)

    await manager.disconnect(ws)

    assert manager.connection_count == 0


@pytest.mark.asyncio
async def test_broadcast_sends_to_all_connections():
    manager = ConnectionManager()
    ws1, ws2 = FakeWebSocket(), FakeWebSocket()
    await manager.connect(ws1)
    await manager.connect(ws2)

    await manager.broadcast("hello")

    assert ws1.sent_messages == ["hello"]
    assert ws2.sent_messages == ["hello"]


@pytest.mark.asyncio
async def test_broadcast_with_no_connections_does_not_raise():
    manager = ConnectionManager()
    await manager.broadcast("hello")  # must not raise


@pytest.mark.asyncio
async def test_broadcast_drops_dead_connections_without_affecting_others():
    manager = ConnectionManager()
    healthy = FakeWebSocket()
    dead = FakeWebSocket(fail_on_send=True)
    await manager.connect(healthy)
    await manager.connect(dead)

    await manager.broadcast("hello")

    assert healthy.sent_messages == ["hello"]
    assert manager.connection_count == 1  # dead connection was pruned
