"""WebSocket Real-Time Gateway Router (TASK-4.3)."""

from __future__ import annotations

import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from server.core.websocket import ws_manager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websockets"])


@router.websocket("/ws/projects/{project_id}")
async def project_websocket_endpoint(
    websocket: WebSocket,
    project_id: str,
) -> None:
    """Real-time WebSocket endpoint streaming RFC 6902 JSON patch deltas for a project."""
    await ws_manager.connect(websocket, project_id)

    try:
        # Send connection confirmation handshake
        await websocket.send_json(
            {
                "type": "connected",
                "projectId": project_id,
                "message": "Connected to CineForge real-time delta stream",
            }
        )

        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            # Heartbeat handling
            if msg_type == "ping":
                await websocket.send_json({"type": "pong", "timestamp": data.get("timestamp")})
            elif msg_type == "subscribe":
                await websocket.send_json({"type": "subscribed", "projectId": project_id})
            else:
                logger.debug("Received client WebSocket message: %s", data)

    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket, project_id)
    except Exception as exc:
        logger.warning("WebSocket error for project %s: %s", project_id, exc)
        await ws_manager.disconnect(websocket, project_id)
