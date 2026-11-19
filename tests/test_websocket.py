"""Tests for WebSocket Real-Time Gateway & Delta Broadcast (TASK-4.3)."""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from server.core.websocket import ConnectionManager, ws_manager
from server.main import app


def test_websocket_connection_and_heartbeat() -> None:
    client = TestClient(app)
    with client.websocket_connect("/ws/projects/proj_ws_01") as ws:
        # Initial connection acknowledgment
        data = ws.receive_json()
        assert data["type"] == "connected"
        assert data["projectId"] == "proj_ws_01"

        # Ping-pong heartbeat
        ws.send_json({"type": "ping", "timestamp": 1795000000})
        pong = ws.receive_json()
        assert pong["type"] == "pong"
        assert pong["timestamp"] == 1795000000


@pytest.mark.asyncio
async def test_connection_manager_broadcast_patch() -> None:
    manager = ConnectionManager()
    project_id = "proj_test_broadcast"

    class MockWebSocket:
        def __init__(self):
            self.sent_messages = []

        async def accept(self):
            pass

        async def send_json(self, msg):
            self.sent_messages.append(msg)

    mock_ws = MockWebSocket()
    await manager.connect(mock_ws, project_id)  # type: ignore

    patch_delta = [{"op": "replace", "path": "/scenes/0/video/status", "value": "completed"}]
    await manager.broadcast_patch(project_id, patch_delta, version=4)

    assert len(mock_ws.sent_messages) == 1
    msg = mock_ws.sent_messages[0]
    assert msg["type"] == "patch"
    assert msg["projectId"] == project_id
    assert msg["version"] == 4
    assert msg["patches"] == patch_delta

    await manager.disconnect(mock_ws, project_id)  # type: ignore
    assert project_id not in manager.active_connections
