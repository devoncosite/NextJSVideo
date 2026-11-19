"""Tests for Invalidation Graph, Task Reaper & Security Hardening (Phase 8)."""

from __future__ import annotations

import time
import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from server.core.invalidation import compute_downstream_invalidations, invalidate_manifest_node
from server.core.reaper import recover_orphaned_tasks
from server.core.security_middleware import RateLimiterMiddleware
from server.main import app
from server.models import Base
from server.models.job import JobQueueRecord, JobStage, JobStatus
from server.models.project import Project, ProjectStatus
from server.routers.context import DEFAULT_USER_ID, ensure_default_user_exists


@pytest.fixture
async def hardening_test_db():
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    @event.listens_for(test_engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        await ensure_default_user_exists(session)

    yield session_factory
    await test_engine.dispose()


@pytest.mark.asyncio
async def test_dependency_invalidation_graph(hardening_test_db) -> None:
    """TASK-8.1: Invalidate Character 1; assert referencing scenes reset while others stay untouched."""
    manifest = {
        "projectId": "proj_invalidation_test",
        "version": 1,
        "consistencies": {
            "characters": [
                {"id": "char_01", "name": "Elena"},
                {"id": "char_02", "name": "Marcus"},
            ],
            "objects": [],
        },
        "scenes": [
            {
                "id": "scene_01",
                "keyframe": {
                    "refIds": ["char_01"],
                    "status": "completed",
                    "selectedAssetUrl": "http://img/s1.png",
                },
                "audio": {"status": "completed", "mergedSceneAudioUrl": "http://aud/s1.m4a"},
                "video": {
                    "status": "completed",
                    "rawVideoUrl": "http://vid/s1.mp4",
                    "requiresLipSync": False,
                },
            },
            {
                "id": "scene_02",
                "keyframe": {
                    "refIds": ["char_02"],
                    "status": "completed",
                    "selectedAssetUrl": "http://img/s2.png",
                },
                "audio": {"status": "completed", "mergedSceneAudioUrl": "http://aud/s2.m4a"},
                "video": {
                    "status": "completed",
                    "rawVideoUrl": "http://vid/s2.mp4",
                    "requiresLipSync": False,
                },
            },
        ],
        "assembly": {
            "status": "completed",
            "finalVideoUrl": "http://vid/master.mp4",
            "bundleZipUrl": "http://zip/bundle.zip",
        },
    }

    async with hardening_test_db() as db:
        project = Project(
            id="proj_invalidation_test",
            user_id=DEFAULT_USER_ID,
            title="DAG Invalidation Test",
            format="cinematic_drama",
            version=1,
            status=ProjectStatus.COMPLETED,
            manifest=manifest,
        )
        db.add(project)
        await db.commit()

        # Invalidate Character 1 (/consistencies/characters/0)
        updated_project, patches = await invalidate_manifest_node(
            project_id=project.id,
            node_path="/consistencies/characters/0",
            db=db,
        )

        m = updated_project.manifest

        # Scene 1 referenced char_01 -> must be invalidated
        assert m["scenes"][0]["keyframe"]["status"] == "idle"
        assert m["scenes"][0]["keyframe"]["selectedAssetUrl"] is None
        assert m["scenes"][0]["video"]["status"] == "idle"
        # Audio for Scene 1 was not invalidated
        assert m["scenes"][0]["audio"]["status"] == "completed"

        # Scene 2 referenced char_02 -> must remain completed!
        assert m["scenes"][1]["keyframe"]["status"] == "completed"
        assert m["scenes"][1]["video"]["status"] == "completed"

        # Assembly must be invalidated
        assert m["assembly"]["status"] == "idle"
        assert m["assembly"]["finalVideoUrl"] is None
        assert updated_project.status == ProjectStatus.DRAFT


@pytest.mark.asyncio
async def test_orphan_task_reaper(hardening_test_db) -> None:
    """TASK-8.2: Verify crashed tasks missing heartbeats are requeued or marked failed."""
    async with hardening_test_db() as db:
        project = Project(
            id="proj_reaper_test",
            user_id=DEFAULT_USER_ID,
            title="Reaper Test",
            format="cinematic_drama",
            version=1,
            status=ProjectStatus.DRAFT,
            manifest={},
        )
        db.add(project)

        # Job 1: Attempt 0 -> Should be requeued (attempt 1)
        job1 = JobQueueRecord(
            id=uuid.uuid4(),
            project_id=project.id,
            stage=JobStage.KEYFRAMES,
            target_id="kf_batch",
            arq_job_id="arq_crashed_1",
            status=JobStatus.RUNNING,
            retry_count=0,
        )
        # Job 2: Attempt 3 -> Exceeded retries, should be marked FAILED
        job2 = JobQueueRecord(
            id=uuid.uuid4(),
            project_id=project.id,
            stage=JobStage.VIDEO,
            target_id="vid_batch",
            arq_job_id="arq_crashed_2",
            status=JobStatus.RUNNING,
            retry_count=3,
        )
        db.add_all([job1, job2])
        await db.commit()

        # Run recovery without redis heartbeat
        recovered = await recover_orphaned_tasks(db=db, redis_client=None, max_retries=3)
        assert len(recovered) == 2

        stmt = select(JobQueueRecord).order_by(JobQueueRecord.created_at)
        records = list((await db.execute(stmt)).scalars().all())

        j1 = next(r for r in records if r.arq_job_id == "arq_crashed_1")
        assert j1.status == JobStatus.QUEUED
        assert j1.retry_count == 1
        assert "requeued" in j1.error_message.lower()

        j2 = next(r for r in records if r.arq_job_id == "arq_crashed_2")
        assert j2.status == JobStatus.FAILED
        assert j2.retry_count == 3
        assert "exceeded" in j2.error_message.lower()


@pytest.mark.asyncio
async def test_security_headers_and_rate_limiting() -> None:
    """TASK-8.3: Verify security headers and rate limiter response on rapid requests."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Health check returns security headers
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.headers["X-Content-Type-Options"] == "nosniff"
        assert resp.headers["X-Frame-Options"] == "DENY"
        assert "default-src 'self'" in resp.headers["Content-Security-Policy"]

        # 2. Rate limiter test: using small rate limiter instance to trigger 429
        from fastapi import FastAPI
        mini_app = FastAPI()
        mini_app.add_middleware(RateLimiterMiddleware, default_limit=3, generation_limit=2)

        @mini_app.get("/ping")
        async def ping():
            return {"msg": "pong"}

        mini_transport = ASGITransport(app=mini_app)
        async with AsyncClient(transport=mini_transport, base_url="http://testserver") as mclient:
            # First 3 requests succeed
            for _ in range(3):
                r = await mclient.get("/ping")
                assert r.status_code == 200

            # 4th request exceeds limit -> 429 Too Many Requests
            r4 = await mclient.get("/ping")
            assert r4.status_code == 429
            assert "Retry-After" in r4.headers
