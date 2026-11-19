"""WebSocket Connection Manager & Redis Pub/Sub Delta Forwarder (TASK-4.3)."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional, Set

import redis.asyncio as aioredis
from fastapi import WebSocket, WebSocketDisconnect

from server.core.config import get_settings
from workers.utils.manifest_updater import get_project_channel

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages active WebSockets and bridges Redis Pub/Sub channels to connected frontend clients."""

    def __init__(self) -> None:
        # project_id -> Set of active WebSocket connections
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        # project_id -> asyncio.Task running Redis pub/sub listener
        self._listener_tasks: Dict[str, asyncio.Task] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, project_id: str) -> None:
        """Accept WebSocket connection and subscribe to project updates if needed."""
        await websocket.accept()
        async with self._lock:
            if project_id not in self.active_connections:
                self.active_connections[project_id] = set()
            self.active_connections[project_id].add(websocket)

            # Spawn Redis Pub/Sub listener for this project if not already running
            if project_id not in self._listener_tasks or self._listener_tasks[project_id].done():
                self._listener_tasks[project_id] = asyncio.create_task(
                    self._subscribe_to_redis(project_id)
                )

        logger.info("WebSocket connected for project %s (total: %d)", project_id, len(self.active_connections[project_id]))

    async def disconnect(self, websocket: WebSocket, project_id: str) -> None:
        """Deregister WebSocket connection and cancel listener if project has no remaining clients."""
        async with self._lock:
            if project_id in self.active_connections:
                self.active_connections[project_id].discard(websocket)
                if not self.active_connections[project_id]:
                    del self.active_connections[project_id]
                    # Cancel Redis subscription for this project
                    task = self._listener_tasks.pop(project_id, None)
                    if task and not task.done():
                        task.cancel()

        logger.info("WebSocket disconnected for project %s", project_id)

    async def broadcast_json(self, project_id: str, message: Dict[str, Any]) -> None:
        """Broadcast arbitrary JSON payload to all active WebSockets on this project."""
        conns = list(self.active_connections.get(project_id, []))
        if not conns:
            return

        dead_sockets: List[WebSocket] = []
        for ws in conns:
            try:
                await ws.send_json(message)
            except Exception:
                dead_sockets.append(ws)

        if dead_sockets:
            async with self._lock:
                for dead_ws in dead_sockets:
                    if project_id in self.active_connections:
                        self.active_connections[project_id].discard(dead_ws)

    async def broadcast_patch(
        self,
        project_id: str,
        patches: List[Dict[str, Any]],
        version: int,
    ) -> None:
        """Broadcast RFC 6902 JSON patch delta."""
        payload = {
            "type": "patch",
            "projectId": project_id,
            "version": version,
            "patches": patches,
        }
        await self.broadcast_json(project_id, payload)

    async def _subscribe_to_redis(self, project_id: str) -> None:
        """Background task listening to Redis Pub/Sub and broadcasting deltas to WebSockets."""
        settings = get_settings()
        channel_name = get_project_channel(project_id)
        redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)

        try:
            pubsub = redis_client.pubsub()
            await pubsub.subscribe(channel_name)
            logger.info("Subscribed to Redis channel %s for WebSockets", channel_name)

            async for message in pubsub.listen():
                if message and message.get("type") == "message":
                    raw_data = message.get("data")
                    try:
                        parsed = json.loads(raw_data)
                        await self.broadcast_json(project_id, parsed)
                    except Exception as exc:
                        logger.warning("Error forwarding Redis pub/sub delta: %s", exc)
        except asyncio.CancelledError:
            logger.info("Redis listener task for project %s cancelled", project_id)
        except Exception as exc:
            logger.warning("Redis subscription error for project %s: %s", project_id, exc)
        finally:
            try:
                await redis_client.aclose()
            except Exception:
                pass


# Global singleton manager
ws_manager = ConnectionManager()
