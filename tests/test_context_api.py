"""Tests for FastAPI Context Ingestion API & Content-Addressed Deduplication (TASK-3.1)."""

from __future__ import annotations

import hashlib
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, Optional

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from server.core.database import get_db_session
from server.core.storage import StorageService
from server.main import app
from server.models import Base
from server.routers.context import get_storage_service


class InMemoryMinIOBucket:
    """Mock storage capturing uploads in memory."""

    def __init__(self) -> None:
        self.objects: Dict[str, bytes] = {}

    async def upload_file(
        self,
        file_path: str,
        bucket: str,
        object_key: str,
        ExtraArgs: Optional[Dict[str, Any]] = None,
    ) -> None:
        from pathlib import Path
        self.objects[f"{bucket}/{object_key}"] = Path(file_path).read_bytes()


@pytest.fixture
async def test_db_session():
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    @event.listens_for(test_engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    async def _get_test_db():
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    yield _get_test_db
    await test_engine.dispose()


@pytest.fixture
def mock_storage():
    bucket = InMemoryMinIOBucket()

    @asynccontextmanager
    async def s3_factory():
        yield bucket

    return StorageService(s3_client_factory=s3_factory)


@pytest.mark.asyncio
async def test_context_upload_deduplication_and_crud(test_db_session, mock_storage) -> None:
    """TASK-3.1 Verification: Upload same document twice; second upload must return cached artifact immediately."""
    app.dependency_overrides[get_db_session] = test_db_session
    app.dependency_overrides[get_storage_service] = lambda: mock_storage

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        project_id = "proj_test_context_01"
        file_content = b"Elena Vance investigated the signal across the Pacific coastline."
        expected_hash = hashlib.sha256(file_content).hexdigest()

        # 1. First upload -> brand new artifact
        files = {"file": ("production_brief.txt", file_content, "text/plain")}
        resp1 = await client.post(f"/api/v1/projects/{project_id}/context/upload", files=files)
        assert resp1.status_code == 200, resp1.text
        data1 = resp1.json()
        assert data1["cached"] is False
        assert data1["content_hash"] == expected_hash
        assert data1["project_id"] == project_id
        artifact_id = data1["id"]
        assert artifact_id.startswith("ctx_")
        assert "Elena Vance" in (data1["extracted_markdown"] or "")
        assert data1["summary_json"] is not None

        # 2. Second upload with identical bytes -> returns cached artifact
        files2 = {"file": ("production_brief_copy.txt", file_content, "text/plain")}
        resp2 = await client.post(f"/api/v1/projects/{project_id}/context/upload", files=files2)
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2["cached"] is True
        assert data2["id"] == artifact_id
        assert data2["content_hash"] == expected_hash

        # 3. List context artifacts for project
        list_resp = await client.get(f"/api/v1/projects/{project_id}/context")
        assert list_resp.status_code == 200
        artifacts = list_resp.json()
        assert len(artifacts) == 1
        assert artifacts[0]["id"] == artifact_id

        # 4. Fetch artifact by ID
        get_resp = await client.get(f"/api/v1/context/{artifact_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["id"] == artifact_id

        # 5. Delete artifact
        del_resp = await client.delete(f"/api/v1/projects/{project_id}/context/{artifact_id}")
        assert del_resp.status_code == 200

        # 6. Verify deleted
        get_deleted = await client.get(f"/api/v1/context/{artifact_id}")
        assert get_deleted.status_code == 404

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_context_url_ssrf_rejection(test_db_session, mock_storage) -> None:
    """TASK-3.3 Verification: Crawling private/loopback URL must trigger HTTP 403 Forbidden."""
    app.dependency_overrides[get_db_session] = test_db_session
    app.dependency_overrides[get_storage_service] = lambda: mock_storage

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.post(
            "/api/v1/projects/proj_ssrf_test/context/url",
            json={"url": "http://127.0.0.1:8008/api/health"},
        )
        assert resp.status_code == 403
        assert "SSRF validation" in resp.json()["detail"]

    app.dependency_overrides.clear()
