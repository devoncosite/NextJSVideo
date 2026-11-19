"""Tests for Enterprise Asset Downloader & S3/R2 Storage Service (TASK-1.5)."""

from __future__ import annotations

from contextlib import asynccontextmanager
import hashlib
from pathlib import Path
from typing import Any, AsyncIterator, Dict, Optional

import httpx
import pytest

from server.core.config import Settings
from server.core.storage import AssetDownloadError, StorageService


class InMemoryMinIOBucket:
    """In-memory S3/MinIO mock capturing streaming uploads and headers."""

    def __init__(self) -> None:
        self.objects: Dict[str, bytes] = {}
        self.extra_args: Dict[str, Dict[str, Any]] = {}

    async def upload_file(
        self,
        file_path: str,
        bucket: str,
        object_key: str,
        ExtraArgs: Optional[Dict[str, Any]] = None,
    ) -> None:
        data = Path(file_path).read_bytes()
        full_key = f"{bucket}/{object_key}"
        self.objects[full_key] = data
        self.extra_args[full_key] = ExtraArgs or {}


@pytest.mark.asyncio
async def test_streaming_asset_download_and_sha256_integrity() -> None:
    """TASK-1.5: Stream multi-megabyte video payload from remote CDN to S3/MinIO and verify SHA-256 match."""
    # Generate deterministic 5 MB binary video payload
    chunk = b"CINEFORGE_MP4_FRAME_BLOCK_0123456789ABCDEF" * 1024
    video_payload = chunk * 120  # ~5.2 MB
    expected_sha256 = hashlib.sha256(video_payload).hexdigest()

    minio_bucket = InMemoryMinIOBucket()

    @asynccontextmanager
    async def s3_factory() -> AsyncIterator[InMemoryMinIOBucket]:
        yield minio_bucket

    async def mock_cdn_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            headers={"Content-Type": "video/mp4"},
            content=video_payload,
        )

    settings = Settings(
        S3_BUCKET_NAME="studio-assets",
        S3_PUBLIC_CDN_URL="http://127.0.0.1:9000/studio-assets",
    )
    storage = StorageService(
        settings=settings,
        s3_client_factory=s3_factory,
        http_transport=httpx.MockTransport(mock_cdn_handler),
    )

    public_url = await storage.download_and_persist_asset(
        remote_url="https://replicate.delivery/pbxt/mock-video-output.mp4",
        project_id="proj_98a7f",
        subfolder="videos",
        extension="mp4",
    )

    expected_key = f"/proj_98a7f/videos/{expected_sha256}.mp4"
    assert public_url == f"http://127.0.0.1:9000/studio-assets{expected_key}"
    assert storage.last_persisted is not None
    assert storage.last_persisted.sha256 == expected_sha256
    assert storage.last_persisted.size_bytes == len(video_payload)

    bucket_key = f"studio-assets/proj_98a7f/videos/{expected_sha256}.mp4"
    assert bucket_key in minio_bucket.objects
    persisted_sha256 = hashlib.sha256(minio_bucket.objects[bucket_key]).hexdigest()
    assert persisted_sha256 == expected_sha256
    assert minio_bucket.extra_args[bucket_key]["ContentType"] == "video/mp4"
    assert minio_bucket.extra_args[bucket_key]["CacheControl"] == "public, max-age=31536000, immutable"


@pytest.mark.asyncio
async def test_expired_cdn_403_404_retry_and_error() -> None:
    """TASK-1.5: Verify retry behavior and AssetDownloadError on 403/404 CDN expiration."""
    attempts = 0

    async def expired_cdn_handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(status_code=403, content=b"URL expired")

    minio_bucket = InMemoryMinIOBucket()

    @asynccontextmanager
    async def s3_factory() -> AsyncIterator[InMemoryMinIOBucket]:
        yield minio_bucket

    storage = StorageService(
        s3_client_factory=s3_factory,
        http_transport=httpx.MockTransport(expired_cdn_handler),
        max_retries=3,
        retry_base_delay=0.01,
    )

    with pytest.raises(AssetDownloadError) as exc_info:
        await storage.download_and_persist_asset(
            remote_url="https://fal.media/files/expired_asset.png",
            project_id="proj_98a7f",
            subfolder="keyframes",
            extension="png",
        )

    assert exc_info.value.status_code == 403
    assert attempts == 3
