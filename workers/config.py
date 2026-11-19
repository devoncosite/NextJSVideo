"""ARQ Distributed Worker Configuration & Redis Connection Settings (TASK-4.1)."""

from __future__ import annotations

import os
from urllib.parse import urlparse
from arq.connections import RedisSettings

from server.core.config import get_settings


def get_redis_settings() -> RedisSettings:
    """Parse configured Redis connection URL into ARQ RedisSettings."""
    settings = get_settings()
    parsed = urlparse(settings.REDIS_URL)

    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 6379
    password = parsed.password or None
    database = 0

    if parsed.path and parsed.path.strip("/"):
        try:
            database = int(parsed.path.strip("/"))
        except ValueError:
            database = 0

    return RedisSettings(
        host=host,
        port=port,
        database=database,
        password=password,
        conn_timeout=10,
    )


# Worker concurrency and execution parameters
DEFAULT_JOB_TIMEOUT_SECONDS: int = 600  # 10 minutes max per generation stage
MAX_CONCURRENT_JOBS: int = 20
KEEP_RESULT_SECONDS: int = 3600  # Retain completed job state for 1 hour

# Provider-specific rate limiting semaphores to prevent API 429 errors
PROVIDER_SEMAPHORE_LIMITS = {
    "replicate": 5,
    "fal_ai": 5,
    "elevenlabs": 5,
    "gemini": 10,
    "synclabs": 3,
}
