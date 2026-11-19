"""Production Observability, Prometheus Metrics & Telemetry (TASK-10.3)."""

from __future__ import annotations

import logging
import time
from typing import Dict, List, Optional
from fastapi import APIRouter, Request, Response

logger = logging.getLogger(__name__)

# Lightweight in-memory metric collectors
_request_counts: Dict[str, int] = {}
_request_latency_sum: Dict[str, float] = {}
_request_latency_count: Dict[str, int] = {}
_active_tasks_gauge = 0
_queue_depth_gauge = 0


def record_request_metric(method: str, path: str, status_code: int, duration_sec: float) -> None:
    """Record HTTP request metric counters and durations."""
    # Group parameterized endpoints
    normalized_path = path
    if normalized_path.startswith("/api/v1/projects/"):
        parts = normalized_path.split("/")
        if len(parts) > 4:
            normalized_path = f"/api/v1/projects/:id/{'/'.join(parts[5:])}"
        else:
            normalized_path = "/api/v1/projects/:id"

    key = f'method="{method}",path="{normalized_path}",status="{status_code}"'
    _request_counts[key] = _request_counts.get(key, 0) + 1

    latency_key = f'method="{method}",path="{normalized_path}"'
    _request_latency_sum[latency_key] = _request_latency_sum.get(latency_key, 0.0) + duration_sec
    _request_latency_count[latency_key] = _request_latency_count.get(latency_key, 0) + 1


def set_active_tasks_metric(count: int) -> None:
    """Set gauge of active ARQ worker generation tasks."""
    global _active_tasks_gauge
    _active_tasks_gauge = max(0, count)


def set_queue_depth_metric(depth: int) -> None:
    """Set gauge of pending tasks in Redis queue."""
    global _queue_depth_gauge
    _queue_depth_gauge = max(0, depth)


router = APIRouter(tags=["Telemetry"])


@router.get("/metrics")
async def prometheus_metrics() -> Response:
    """Expose Prometheus formatted metrics for scrapers."""
    lines: List[str] = [
        "# HELP cineforge_http_requests_total Total number of HTTP requests processed.",
        "# TYPE cineforge_http_requests_total counter",
    ]
    for labels, count in _request_counts.items():
        lines.append(f"cineforge_http_requests_total{{{labels}}} {count}")

    lines.extend([
        "# HELP cineforge_http_request_duration_seconds Total time spent in HTTP requests.",
        "# TYPE cineforge_http_request_duration_seconds summary",
    ])
    for labels, sum_dur in _request_latency_sum.items():
        count = _request_latency_count.get(labels, 1)
        lines.append(f"cineforge_http_request_duration_seconds_sum{{{labels}}} {sum_dur:.4f}")
        lines.append(f"cineforge_http_request_duration_seconds_count{{{labels}}} {count}")

    lines.extend([
        "# HELP cineforge_active_worker_tasks Number of tasks currently executing in ARQ workers.",
        "# TYPE cineforge_active_worker_tasks gauge",
        f"cineforge_active_worker_tasks {_active_tasks_gauge}",
        "# HELP cineforge_queue_depth Total number of jobs waiting in Redis queue.",
        "# TYPE cineforge_queue_depth gauge",
        f"cineforge_queue_depth {_queue_depth_gauge}",
    ])

    body = "\n".join(lines) + "\n"
    return Response(content=body, media_type="text/plain; version=0.0.4; charset=utf-8")
