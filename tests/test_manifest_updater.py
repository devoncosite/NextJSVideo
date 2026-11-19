"""Tests for Job Lifecycle, State Machine & Manifest Updater (TASK-4.2)."""

from __future__ import annotations

import uuid
from typing import Any, Dict

import pytest
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from server.models import Base, JobQueueRecord, JobStage, JobStatus, Project, ProjectStatus, User
from workers.utils.manifest_updater import (
    safe_worker_execution,
    update_manifest_node,
    update_node_status,
)


@pytest.fixture
async def test_session():
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
        user = User(
            id=uuid.uuid4(),
            email="producer@cineforge.ai",
            hashed_password="hashed_val",
            name="Studio Producer",
        )
        session.add(user)
        await session.flush()

        initial_manifest = {
            "projectId": "proj_worker_test",
            "version": 1,
            "scenes": [
                {
                    "sceneNumber": 1,
                    "video": {
                        "status": "idle",
                        "progressPercent": 0,
                        "selectedAssetUrl": None,
                        "error": None,
                    },
                }
            ],
        }

        project = Project(
            id="proj_worker_test",
            user_id=user.id,
            title="Worker Pipeline Test",
            format="cinematic_drama",
            version=1,
            manifest=initial_manifest,
            status=ProjectStatus.DRAFT,
        )
        session.add(project)
        await session.commit()

    yield session_factory
    await test_engine.dispose()


@pytest.mark.asyncio
async def test_update_manifest_node_increments_version(test_session) -> None:
    async with test_session() as session:
        proj = await update_manifest_node(
            project_id="proj_worker_test",
            path="/scenes/0/video/progressPercent",
            value=80,
            db=session,
        )
        assert proj.version == 2
        assert proj.manifest["scenes"][0]["video"]["progressPercent"] == 80


@pytest.mark.asyncio
async def test_update_node_status_batch(test_session) -> None:
    async with test_session() as session:
        proj = await update_node_status(
            project_id="proj_worker_test",
            base_path="/scenes/0/video",
            status="completed",
            progress=100,
            asset_url="http://127.0.0.1:9000/studio-assets/scene_01.mp4",
            db=session,
        )
        assert proj.version == 2
        video_node = proj.manifest["scenes"][0]["video"]
        assert video_node["status"] == "completed"
        assert video_node["progressPercent"] == 100
        assert video_node["selectedAssetUrl"] == "http://127.0.0.1:9000/studio-assets/scene_01.mp4"


@pytest.mark.asyncio
async def test_safe_worker_execution_catches_exception_and_marks_failed(test_session) -> None:
    async with test_session() as session:
        with pytest.raises(RuntimeError, match="Replicate API 500 error"):
            async with safe_worker_execution(
                project_id="proj_worker_test",
                base_path="/scenes/0/video",
                stage=JobStage.VIDEO,
                target_id="scene_01",
                arq_job_id="job_err_01",
                db=session,
            ):
                raise RuntimeError("Replicate API 500 error")

    # Verify that node flipped to "failed" and JobQueueRecord is recorded as FAILED
    async with test_session() as session:
        proj = (await session.execute(select(Project).where(Project.id == "proj_worker_test"))).scalar_one()
        video_node = proj.manifest["scenes"][0]["video"]
        assert video_node["status"] == "failed"
        assert "Replicate API 500 error" in video_node["error"]

        jobs = (await session.execute(select(JobQueueRecord))).scalars().all()
        assert len(jobs) == 1
        assert jobs[0].status == JobStatus.FAILED
        assert "Replicate API 500 error" in (jobs[0].error_message or "")
