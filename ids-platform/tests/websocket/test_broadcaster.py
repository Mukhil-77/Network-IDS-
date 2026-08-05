"""Unit tests for AlertBroadcaster - the sync-thread-to-asyncio bridge (see broadcaster.py's docstring)."""

import asyncio
import json
import threading

import pytest

from backend.websocket.broadcaster import AlertBroadcaster
from backend.websocket.manager import ConnectionManager


@pytest.mark.asyncio
async def test_broadcast_alert_serializes_and_sends():
    manager = ConnectionManager()
    broadcaster = AlertBroadcaster(manager)

    sent = []

    class FakeWS:
        async def accept(self):
            pass

        async def send_text(self, message):
            sent.append(message)

    ws = FakeWS()
    await manager.connect(ws)

    await broadcaster.broadcast_alert({"attack": "DoS", "confidence": 95.0})

    assert len(sent) == 1
    event = json.loads(sent[0])
    assert event["type"] == "alert"
    assert event["payload"] == {"attack": "DoS", "confidence": 95.0}


def test_publish_alert_threadsafe_without_bound_loop_does_not_raise():
    broadcaster = AlertBroadcaster(ConnectionManager())
    # No bind_loop() call - must log and return, never raise, even called from a plain thread.
    broadcaster.publish_alert_threadsafe({"attack": "DoS"})


def test_publish_alert_threadsafe_from_a_worker_thread_reaches_the_bound_loop():
    manager = ConnectionManager()
    broadcaster = AlertBroadcaster(manager)
    received = []

    class FakeWS:
        async def accept(self):
            pass

        async def send_text(self, message):
            received.append(message)

    async def scenario():
        ws = FakeWS()
        await manager.connect(ws)
        broadcaster.bind_loop(asyncio.get_running_loop())

        # Simulate a DetectionService worker thread publishing an alert.
        thread = threading.Thread(target=broadcaster.publish_alert_threadsafe, args=({"attack": "PortScan"},))
        thread.start()
        thread.join()

        # The broadcast was scheduled via run_coroutine_threadsafe onto this
        # loop but hasn't necessarily run yet - give the loop one tick.
        await asyncio.sleep(0.05)

    asyncio.run(scenario())
    assert len(received) == 1
    assert json.loads(received[0])["payload"] == {"attack": "PortScan"}
