"""Content-Addressed File Ingestion Pipeline & SHA-256 Hashing (TASK-3.1)."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import AsyncIterator, Tuple, Union


class StreamingHasher:
    """Incremental SHA-256 calculator tracking byte count and cryptographic digest."""

    def __init__(self) -> None:
        self._hasher = hashlib.sha256()
        self._bytes_read: int = 0

    def update(self, chunk: bytes) -> None:
        """Process an incoming byte slice."""
        if not chunk:
            return
        self._hasher.update(chunk)
        self._bytes_read += len(chunk)

    @property
    def hexdigest(self) -> str:
        """Return lowercase hexadecimal representation of computed digest."""
        return self._hasher.hexdigest()

    @property
    def total_bytes(self) -> int:
        """Total byte count processed so far."""
        return self._bytes_read


def compute_sha256_bytes(data: bytes) -> str:
    """Compute SHA-256 hex digest of in-memory byte buffer."""
    return hashlib.sha256(data).hexdigest()


async def compute_sha256_stream(
    stream: AsyncIterator[bytes],
) -> Tuple[str, int]:
    """Compute SHA-256 hex digest and total byte count from an async byte iterator."""
    hasher = StreamingHasher()
    async for chunk in stream:
        hasher.update(chunk)
    return hasher.hexdigest, hasher.total_bytes


async def compute_sha256_file(
    file_path: Union[str, Path],
    chunk_size: int = 64 * 1024,
) -> Tuple[str, int]:
    """Stream file from disk to compute SHA-256 digest and total file size."""
    path = Path(file_path)
    hasher = StreamingHasher()
    with path.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest, hasher.total_bytes
