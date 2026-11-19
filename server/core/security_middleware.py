"""Production Security Hardening & Rate Limiting Middleware (TASK-8.3)."""

from __future__ import annotations

import logging
import time
from typing import Callable, Dict, Optional

from fastapi import FastAPI, HTTPException, Request, Response, status
import redis.asyncio as aioredis
from starlette.middleware.base import BaseHTTPMiddleware

from server.core.config import get_settings

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Enforce strict production HTTP security headers and Content Security Policy."""

    async def dispatch(self, request: Request, call_next: Callable[[Request], Response]) -> Response:
        response = await call_next(request)

        # Set standard security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "img-src 'self' data: blob: https:; "
            "media-src 'self' blob: https:; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline';"
        )
        return response


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """Sliding-window rate limiter utilizing Redis (or in-memory fallback for local dev)."""

    def __init__(
        self,
        app: FastAPI,
        redis_client: Optional[aioredis.Redis] = None,
        default_limit: int = 100,
        generation_limit: int = 10,
        window_seconds: int = 60,
    ) -> None:
        super().__init__(app)
        self.redis_client = redis_client
        self.default_limit = default_limit
        self.generation_limit = generation_limit
        self.window_seconds = window_seconds
        # In-memory fallback dictionary: key -> List[timestamp]
        self._memory_cache: Dict[str, list[float]] = {}

    async def _is_rate_limited(self, client_ip: str, is_generation: bool) -> bool:
        limit = self.generation_limit if is_generation else self.default_limit
        key = f"rate_limit:{client_ip}:{'gen' if is_generation else 'std'}"
        now = time.time()

        if self.redis_client is not None:
            try:
                pipe = self.redis_client.pipeline()
                window_start = now - self.window_seconds
                # Remove timestamps older than window
                pipe.zremrangebyscore(key, 0, window_start)
                # Count remaining items
                pipe.zcard(key)
                # Add current request
                pipe.zadd(key, {str(now): now})
                # Set TTL
                pipe.expire(key, self.window_seconds)
                results = await pipe.execute()
                current_count = results[1]
                return current_count >= limit
            except Exception as exc:
                logger.warning("Redis rate limiter failed (%s); falling back to in-memory limit.", exc)

        # In-memory sliding window fallback
        timestamps = self._memory_cache.setdefault(key, [])
        cutoff = now - self.window_seconds
        self._memory_cache[key] = [ts for ts in timestamps if ts > cutoff]

        if len(self._memory_cache[key]) >= limit:
            return True

        self._memory_cache[key].append(now)
        return False

    async def dispatch(self, request: Request, call_next: Callable[[Request], Response]) -> Response:
        # Bypass rate limit on health checks
        if request.url.path in ("/health", "/api/health"):
            return await call_next(request)

        client_ip = request.client.host if request.client else "127.0.0.1"
        is_generation = "/pipeline/" in request.url.path and request.method == "POST"

        # Check content length limits: 500MB for media upload, 2MB for general JSON
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                length_bytes = int(content_length)
                is_upload = "/upload" in request.url.path
                max_bytes = 500 * 1024 * 1024 if is_upload else 2 * 1024 * 1024
                if length_bytes > max_bytes:
                    return Response(
                        content=f"Payload Too Large: maximum allowed size is {max_bytes} bytes",
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    )
            except ValueError:
                pass

        if await self._is_rate_limited(client_ip, is_generation):
            return Response(
                content="Too Many Requests: rate limit exceeded. Please wait before retrying.",
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                headers={"Retry-After": str(self.window_seconds)},
            )

        return await call_next(request)
