"""
WS /ws/alerts

Every connected client receives a WSEvent(type="alert", payload=<Alert>)
message the instant AlertService broadcasts one - no polling. The server
never expects messages *from* the client beyond the initial handshake;
`receive_text()` is only called to detect disconnects (a closed socket
raises WebSocketDisconnect there).

Milestone 9: authenticated via a `?token=<access_token>` query parameter,
not an Authorization header - browsers cannot set custom headers during
the WebSocket handshake itself, so a query parameter is the standard
approach (the frontend appends its access token when opening the socket -
see frontend/src/services/websocketService.ts). The connection is closed
with code 4401 (a custom application-level close code in the 4000-4999
private-use range) if the token is missing or invalid, before it's ever
added to the connection manager - an unauthenticated client never receives
a single broadcast.
"""

from __future__ import annotations

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from backend.auth.jwt_manager import ACCESS_TOKEN_TYPE, ExpiredTokenError, InvalidTokenError, decode_token
from backend.utils.logger import get_logger
from backend.websocket.manager import connection_manager

logger = get_logger(__name__)
router = APIRouter()

WS_UNAUTHORIZED_CLOSE_CODE = 4401


@router.websocket("/ws/alerts")
async def ws_alerts(websocket: WebSocket, token: str = Query(...)) -> None:
    try:
        decode_token(token, expected_type=ACCESS_TOKEN_TYPE)
    except (InvalidTokenError, ExpiredTokenError) as exc:
        logger.warning("Rejected WebSocket connection: %s", exc)
        await websocket.close(code=WS_UNAUTHORIZED_CLOSE_CODE, reason="Invalid or expired token")
        return

    await connection_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()  # no client->server protocol defined yet; this just detects disconnects
    except WebSocketDisconnect:
        await connection_manager.disconnect(websocket)
