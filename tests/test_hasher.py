"""Tests for Content-Addressed File Ingestion Pipeline & SHA-256 Hashing (TASK-3.1)."""

from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path

import pytest

from server.core.ingestion.hasher import (
    StreamingHasher,
    compute_sha256_bytes,
    compute_sha256_file,
    compute_sha256_stream,
)


def test_sha256_bytes_matches_hashlib() -> None:
    data = b"CineForge Multimodal Context Engine Raw Payload"
    expected = hashlib.sha256(data).hexdigest()
    assert compute_sha256_bytes(data) == expected


@pytest.mark.asyncio
async def test_streaming_hasher_incremental() -> None:
    hasher = StreamingHasher()
    chunks = [b"Chunk 1: Elena Vance", b"Chunk 2: Signal Discovery", b"Chunk 3: Ocean Waves"]
    full_data = b"".join(chunks)

    for chunk in chunks:
        hasher.update(chunk)

    assert hasher.total_bytes == len(full_data)
    assert hasher.hexdigest == hashlib.sha256(full_data).hexdigest()


@pytest.mark.asyncio
async def test_compute_sha256_stream() -> None:
    data_parts = [b"Hello ", b"multimodal ", b"world!"]
    full_data = b"".join(data_parts)

    async def sample_stream():
        for p in data_parts:
            yield p

    digest, total_bytes = await compute_sha256_stream(sample_stream())
    assert total_bytes == len(full_data)
    assert digest == hashlib.sha256(full_data).hexdigest()


@pytest.mark.asyncio
async def test_compute_sha256_file() -> None:
    with tempfile.NamedTemporaryFile(delete=True) as tmp:
        payload = b"Production Bible PDF Mock Payload " * 1000
        tmp.write(payload)
        tmp.flush()

        digest, total_bytes = await compute_sha256_file(tmp.name)
        assert total_bytes == len(payload)
        assert digest == hashlib.sha256(payload).hexdigest()
