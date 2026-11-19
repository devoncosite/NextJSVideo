"""Tests for Prometheus Telemetry and Observability (TASK-10.3)."""

import pytest
from httpx import ASGITransport, AsyncClient

from server.core.telemetry import (
    record_request_metric,
    set_active_tasks_metric,
    set_queue_depth_metric,
)
from server.main import app


@pytest.mark.asyncio
async def test_telemetry_metrics_endpoint():
    """Verify Prometheus metrics export endpoint returns 200 with standard exposition format."""
    # Seed metrics
    record_request_metric("GET", "/api/v1/projects", 200, 0.045)
    record_request_metric("POST", "/api/v1/pipeline/generate-pitch", 201, 1.25)
    set_active_tasks_metric(4)
    set_queue_depth_metric(12)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/metrics")
        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]
        body = response.text

        # Verify Prometheus metric declarations
        assert "cineforge_http_requests_total" in body
        assert "cineforge_active_worker_tasks 4" in body
        assert "cineforge_queue_depth 12" in body
        assert 'method="GET"' in body
