"""Tests for Resilient Asynchronous HTTP Client & 429/503 Retry Backoff (TASK-5.1)."""

from __future__ import annotations

import httpx
import pytest

from server.providers.http_client import ProviderHTTPError, ResilientHTTPClient, parse_retry_after


def test_parse_retry_after_seconds_and_date() -> None:
    assert parse_retry_after("5") == 5.0
    assert parse_retry_after("12.5") == 12.5
    assert parse_retry_after("") is None
    assert parse_retry_after(None) is None


@pytest.mark.asyncio
async def test_resilient_http_client_retries_on_429() -> None:
    call_count = 0

    def mock_handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            return httpx.Response(429, headers={"Retry-After": "0.05"}, text="Rate limit exceeded")
        return httpx.Response(200, json={"status": "success", "attempts": call_count})

    transport = httpx.MockTransport(mock_handler)
    client = ResilientHTTPClient(
        base_url="https://api.mockai.com",
        max_retries=4,
        initial_delay=0.01,
        transport=transport,
    )

    resp = await client.request("POST", "/v1/generate", json_data={"prompt": "test"})
    assert resp.status_code == 200
    assert resp.json()["attempts"] == 3
    await client.close()


@pytest.mark.asyncio
async def test_resilient_http_client_raises_on_persistent_503() -> None:
    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="Service Unavailable")

    transport = httpx.MockTransport(mock_handler)
    client = ResilientHTTPClient(
        base_url="https://api.mockai.com",
        max_retries=3,
        initial_delay=0.01,
        transport=transport,
    )

    with pytest.raises(ProviderHTTPError) as exc_info:
        await client.request("GET", "/v1/status")
    assert exc_info.value.status_code == 503
    await client.close()
