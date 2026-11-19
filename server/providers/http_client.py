"""Resilient Asynchronous HTTP Client with Exponential Backoff & Jitter (TASK-5.1)."""

from __future__ import annotations

import asyncio
import email.utils
import logging
import random
import time
from typing import Any, Dict, Optional, Union

import httpx

logger = logging.getLogger(__name__)


class ProviderHTTPError(Exception):
    """Raised when an external AI provider request fails after all retries."""

    def __init__(self, message: str, status_code: Optional[int] = None, response_body: Optional[str] = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


def parse_retry_after(header_value: Optional[str]) -> Optional[float]:
    """Parse HTTP 'Retry-After' header containing seconds or an RFC 2822 date string."""
    if not header_value:
        return None
    header_clean = header_value.strip()
    # Check if integer seconds
    try:
        return max(0.0, float(header_clean))
    except ValueError:
        pass

    # Try parsing HTTP date
    try:
        date_tuple = email.utils.parsedate(header_clean)
        if date_tuple:
            target_ts = time.mktime(date_tuple)
            delay = target_ts - time.time()
            return max(0.0, delay)
    except Exception:
        pass

    return None


class ResilientHTTPClient:
    """Async HTTP Client with connection pooling, exponential backoff, jitter, and 429/503 retry handling."""

    def __init__(
        self,
        base_url: str = "",
        timeout: float = 60.0,
        max_retries: int = 4,
        initial_delay: float = 0.5,
        backoff_factor: float = 2.0,
        max_delay: float = 30.0,
        transport: Optional[httpx.AsyncBaseTransport] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> None:
        self.base_url = base_url
        self.timeout = timeout
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.backoff_factor = backoff_factor
        self.max_delay = max_delay
        self._transport = transport
        self._default_headers = headers or {}
        self._client: Optional[httpx.AsyncClient] = None

    async def get_client(self) -> httpx.AsyncClient:
        """Return or instantiate underlying httpx.AsyncClient."""
        if self._client is None or self._client.is_closed:
            limits = httpx.Limits(max_connections=50, max_keepalive_connections=20)
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(self.timeout, connect=10.0),
                limits=limits,
                transport=self._transport,
                headers=self._default_headers,
                http2=True,
            )
        return self._client

    async def close(self) -> None:
        """Close connection pool."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        json_data: Optional[Any] = None,
        data: Optional[Any] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> httpx.Response:
        """Execute HTTP request with automated backoff on 429 / 503 / network errors."""
        client = await self.get_client()
        combined_headers = {**self._default_headers, **(headers or {})}

        for attempt in range(1, self.max_retries + 1):
            try:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=combined_headers,
                    json=json_data,
                    data=data,
                    params=params,
                )

                # Success or client errors that shouldn't be retried
                if response.status_code < 400:
                    return response

                # Rate Limit (429) or Server Overloaded / Temporary (502, 503, 504)
                if response.status_code in (429, 502, 503, 504):
                    if attempt == self.max_retries:
                        raise ProviderHTTPError(
                            f"HTTP {response.status_code} from provider after {attempt} attempts: {response.text[:300]}",
                            status_code=response.status_code,
                            response_body=response.text,
                        )

                    retry_header = response.headers.get("Retry-After")
                    explicit_wait = parse_retry_after(retry_header)

                    if explicit_wait is not None:
                        wait_seconds = min(self.max_delay, explicit_wait + random.uniform(0.1, 0.5))
                    else:
                        base_wait = self.initial_delay * (self.backoff_factor ** (attempt - 1))
                        jitter = random.uniform(0.05, 0.5)
                        wait_seconds = min(self.max_delay, base_wait + jitter)

                    logger.warning(
                        "Received HTTP %d from %s (attempt %d/%d). Retrying in %.2fs...",
                        response.status_code,
                        url,
                        attempt,
                        self.max_retries,
                        wait_seconds,
                    )
                    await asyncio.sleep(wait_seconds)
                    continue

                # Non-retriable client errors (400, 401, 403, 404, etc.)
                raise ProviderHTTPError(
                    f"HTTP {response.status_code} error from provider: {response.text[:300]}",
                    status_code=response.status_code,
                    response_body=response.text,
                )

            except (httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout, httpx.PoolTimeout) as exc:
                if attempt == self.max_retries:
                    raise ProviderHTTPError(f"Network error after {attempt} attempts: {exc}") from exc
                wait_seconds = min(self.max_delay, self.initial_delay * (self.backoff_factor ** (attempt - 1)) + random.uniform(0.1, 0.3))
                logger.warning("Network error on %s (attempt %d/%d): %s. Retrying in %.2fs...", url, attempt, self.max_retries, exc, wait_seconds)
                await asyncio.sleep(wait_seconds)

        raise ProviderHTTPError(f"Failed to execute {method} request to {url} after {self.max_retries} retries.")
