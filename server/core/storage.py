"""Enterprise Asset Downloader & S3/R2 Storage Service (TASK-1.5)."""

from __future__ import annotations

import asyncio
import hashlib
import mimetypes
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncIterator, Callable, Dict, Optional

import aioboto3
import httpx

from server.core.config import Settings, get_settings

EXTENSION_MIME_MAP: Dict[str, str] = {
    "mp4": "video/mp4",
    "mov": "video/quicktime",
    "webm": "video/webm",
    "mp3": "audio/mpeg",
    "m4a": "audio/mp4",
    "wav": "audio/wav",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
    "json": "application/json",
    "zip": "application/zip",
}


class AssetDownloadError(Exception):
    """Raised when a remote CDN asset fails to stream or returns expired 403/404 status."""

    def __init__(self, message: str, status_code: Optional[int] = None) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass
class PersistedAssetResult:
    """Detailed metadata from a streaming S3/R2 download_and_persist_asset call."""

    public_url: str
    s3_key: str
    sha256: str
    size_bytes: int
    content_type: str


class StorageService:
    """Streaming asset downloader and S3/Cloudflare R2 persistence engine."""

    CACHE_CONTROL_HEADER = "public, max-age=31536000, immutable"
    CHUNK_SIZE = 64 * 1024  # 64 KB streaming chunks

    def __init__(
        self,
        settings: Optional[Settings] = None,
        s3_client_factory: Optional[Callable[[], object]] = None,
        http_transport: Optional[httpx.AsyncBaseTransport] = None,
        max_retries: int = 3,
        retry_base_delay: float = 0.05,
    ) -> None:
        self.settings = settings or get_settings()
        self._s3_client_factory = s3_client_factory
        self._http_transport = http_transport
        self.max_retries = max_retries
        self.retry_base_delay = retry_base_delay
        self._last_persisted: Optional[PersistedAssetResult] = None

    @property
    def last_persisted(self) -> Optional[PersistedAssetResult]:
        return self._last_persisted

    @staticmethod
    def resolve_content_type(extension: str) -> str:
        clean_ext = extension.lstrip(".").lower()
        if clean_ext in EXTENSION_MIME_MAP:
            return EXTENSION_MIME_MAP[clean_ext]
        guessed, _ = mimetypes.guess_type(f"file.{clean_ext}")
        return guessed or "application/octet-stream"

    @staticmethod
    def build_s3_key(project_id: str, subfolder: str, sha256_hex: str, extension: str) -> str:
        clean_proj = project_id.strip("/")
        clean_sub = subfolder.strip("/")
        clean_ext = extension.lstrip(".").lower()
        return f"/{clean_proj}/{clean_sub}/{sha256_hex}.{clean_ext}"

    def build_public_url(self, s3_key: str) -> str:
        base = self.settings.S3_PUBLIC_CDN_URL.rstrip("/")
        normalized_key = s3_key if s3_key.startswith("/") else f"/{s3_key}"
        return f"{base}{normalized_key}"

    async def download_and_persist_asset(
        self,
        remote_url: str,
        project_id: str,
        subfolder: str,
        extension: str,
    ) -> str:
        """Stream bytes from remote CDN into S3/R2 while computing SHA-256 hash on the fly."""
        clean_ext = extension.lstrip(".").lower()
        content_type = self.resolve_content_type(clean_ext)

        last_exc: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                result = await self._stream_once(
                    remote_url=remote_url,
                    project_id=project_id,
                    subfolder=subfolder,
                    extension=clean_ext,
                    content_type=content_type,
                )
                self._last_persisted = result
                return result.public_url
            except AssetDownloadError as exc:
                last_exc = exc
                if attempt < self.max_retries:
                    await asyncio.sleep(self.retry_base_delay * (2 ** (attempt - 1)))
                else:
                    raise
            except httpx.HTTPError as exc:
                last_exc = AssetDownloadError(f"Network error downloading {remote_url}: {exc}")
                if attempt < self.max_retries:
                    await asyncio.sleep(self.retry_base_delay * (2 ** (attempt - 1)))
                else:
                    raise last_exc from exc

        raise last_exc or AssetDownloadError(f"Failed to download {remote_url}")

    async def _stream_once(
        self,
        remote_url: str,
        project_id: str,
        subfolder: str,
        extension: str,
        content_type: str,
    ) -> PersistedAssetResult:
        hasher = hashlib.sha256()
        total_bytes = 0

        with tempfile.NamedTemporaryFile(prefix="studio_asset_", suffix=f".{extension}", delete=True) as tmp_file:
            tmp_path = Path(tmp_file.name)

            async with httpx.AsyncClient(
                transport=self._http_transport,
                follow_redirects=True,
                timeout=httpx.Timeout(60.0, connect=10.0),
            ) as client:
                async with client.stream("GET", remote_url) as response:
                    if response.status_code in (403, 404):
                        raise AssetDownloadError(
                            f"Remote CDN asset expired or inaccessible (HTTP {response.status_code}) for {remote_url}",
                            status_code=response.status_code,
                        )
                    if response.status_code >= 400:
                        raise AssetDownloadError(
                            f"Remote CDN returned HTTP {response.status_code} for {remote_url}",
                            status_code=response.status_code,
                        )

                    async for chunk in response.aiter_bytes(chunk_size=self.CHUNK_SIZE):
                        if not chunk:
                            continue
                        hasher.update(chunk)
                        tmp_file.write(chunk)
                        total_bytes += len(chunk)

            tmp_file.flush()
            sha256_hex = hasher.hexdigest()
            s3_key = self.build_s3_key(project_id, subfolder, sha256_hex, extension)
            object_key = s3_key.lstrip("/")

            await self._upload_file_to_s3(
                file_path=tmp_path,
                bucket=self.settings.S3_BUCKET_NAME,
                object_key=object_key,
                content_type=content_type,
                sha256_hex=sha256_hex,
            )

        public_url = self.build_public_url(s3_key)
        return PersistedAssetResult(
            public_url=public_url,
            s3_key=s3_key,
            sha256=sha256_hex,
            size_bytes=total_bytes,
            content_type=content_type,
        )

    async def _upload_file_to_s3(
        self,
        file_path: Path,
        bucket: str,
        object_key: str,
        content_type: str,
        sha256_hex: str,
    ) -> None:
        extra_args = {
            "ContentType": content_type,
            "CacheControl": self.CACHE_CONTROL_HEADER,
            "Metadata": {"sha256": sha256_hex},
        }

        if self._s3_client_factory is not None:
            async with self._s3_client_factory() as s3_client:
                await self._stream_to_s3_client(s3_client, file_path, bucket, object_key, extra_args)
            return

        session = aioboto3.Session()
        async with session.client(
            "s3",
            endpoint_url=self.settings.S3_ENDPOINT_URL,
            region_name=self.settings.S3_REGION,
            aws_access_key_id=self.settings.S3_ACCESS_KEY,
            aws_secret_access_key=self.settings.S3_SECRET_KEY,
        ) as s3_client:
            await self._stream_to_s3_client(s3_client, file_path, bucket, object_key, extra_args)

    @classmethod
    async def _stream_to_s3_client(
        cls,
        s3_client: object,
        file_path: Path,
        bucket: str,
        object_key: str,
        extra_args: Dict[str, object],
    ) -> None:
        if hasattr(s3_client, "upload_file"):
            await s3_client.upload_file(  # type: ignore[attr-defined]
                str(file_path),
                bucket,
                object_key,
                ExtraArgs=extra_args,
            )
            return

        with file_path.open("rb") as f:
            await s3_client.put_object(  # type: ignore[attr-defined]
                Bucket=bucket,
                Key=object_key,
                Body=f.read(),
                ContentType=extra_args["ContentType"],
                CacheControl=extra_args["CacheControl"],
                Metadata=extra_args["Metadata"],
            )
