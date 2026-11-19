"""Job Lifecycle, State Machine & Manifest Updater (TASK-4.2)."""

from __future__ import annotations

import copy
import json
import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, List, Optional, Union

import redis.asyncio as aioredis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.core.config import get_settings
from server.core.patch_engine import (
    apply_json_patches,
    create_replace_patch,
    create_status_progress_patch,
    normalize_json_pointer,
)
from server.models.job import JobQueueRecord, JobStage, JobStatus
from server.models.project import Project

logger = logging.getLogger(__name__)


def get_project_channel(project_id: str) -> str:
    """Return canonical Redis pub/sub channel for project delta broadcasts."""
    return f"channel:project:{project_id}"


async def publish_project_delta(
    project_id: str,
    version: int,
    patches: List[Dict[str, Any]],
    redis_client: Optional[aioredis.Redis] = None,
) -> None:
    """Publish RFC 6902 JSON patch delta to Redis Pub/Sub channel."""
    channel = get_project_channel(project_id)
    payload = json.dumps(
        {
            "type": "patch",
            "projectId": project_id,
            "version": version,
            "patches": patches,
        }
    )

    if redis_client is not None:
        try:
            await redis_client.publish(channel, payload)
        except Exception as exc:
            logger.warning("Failed to publish delta via provided redis client: %s", exc)
        return

    # Create ephemeral connection if not provided
    settings = get_settings()
    try:
        r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        async with r:
            await r.publish(channel, payload)
    except Exception as exc:
        logger.warning("Failed to publish project delta to Redis channel %s: %s", channel, exc)


async def update_manifest_patches(
    project_id: str,
    patches: List[Dict[str, Any]],
    db: AsyncSession,
    redis_client: Optional[aioredis.Redis] = None,
) -> Project:
    """Apply an array of RFC 6902 patches to a Project manifest, increment version, and broadcast delta."""
    stmt = select(Project).where(Project.id == project_id)
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()

    if project is None:
        raise ValueError(f"Project with ID '{project_id}' not found.")

    # Apply patches to manifest dict
    current_manifest = copy.deepcopy(project.manifest or {})
    updated_manifest = apply_json_patches(current_manifest, patches, in_place=False)

    project.version += 1
    project.manifest = updated_manifest
    await db.commit()
    await db.refresh(project)

    # Publish delta over Redis Pub/Sub
    await publish_project_delta(
        project_id=project_id,
        version=project.version,
        patches=patches,
        redis_client=redis_client,
    )

    return project


async def update_manifest_node(
    project_id: str,
    path: str,
    value: Any,
    db: AsyncSession,
    redis_client: Optional[aioredis.Redis] = None,
) -> Project:
    """Atomically update a single manifest node by path, incrementing version and publishing patch."""
    patch = create_replace_patch(path, value)
    return await update_manifest_patches(
        project_id=project_id,
        patches=[patch],
        db=db,
        redis_client=redis_client,
    )


async def update_node_status(
    project_id: str,
    base_path: str,
    status: str,
    progress: int,
    db: AsyncSession,
    error: Optional[str] = None,
    asset_url: Optional[str] = None,
    variants: Optional[List[str]] = None,
    redis_client: Optional[aioredis.Redis] = None,
) -> Project:
    """Convenience helper to update node status, progress, and assets with RFC 6902 patches."""
    patches = create_status_progress_patch(
        base_path=base_path,
        status=status,
        progress=progress,
        error=error,
        asset_url=asset_url,
        variants=variants,
    )
    return await update_manifest_patches(
        project_id=project_id,
        patches=patches,
        db=db,
        redis_client=redis_client,
    )


@asynccontextmanager
async def safe_worker_execution(
    project_id: str,
    base_path: str,
    stage: JobStage,
    target_id: str,
    arq_job_id: str,
    db: AsyncSession,
    redis_client: Optional[aioredis.Redis] = None,
) -> AsyncIterator[None]:
    """Context manager intercepting worker errors, updating JobQueueRecord, and marking node as failed."""
    # 1. Record job running
    job_record = JobQueueRecord(
        project_id=project_id,
        stage=stage,
        target_id=target_id,
        arq_job_id=arq_job_id,
        status=JobStatus.RUNNING,
    )
    db.add(job_record)
    await db.flush()

    # Mark node generating
    await update_node_status(
        project_id=project_id,
        base_path=base_path,
        status="generating",
        progress=10,
        db=db,
        redis_client=redis_client,
    )

    try:
        yield
        # If block finishes successfully
        job_record.status = JobStatus.COMPLETED
        await db.commit()
    except Exception as exc:
        logger.exception("Worker job %s failed for %s: %s", arq_job_id, base_path, exc)
        job_record.status = JobStatus.FAILED
        job_record.error_message = str(exc)
        job_record.retry_count += 1
        await db.commit()

        # Mark node failed in manifest and broadcast failure patch
        await update_node_status(
            project_id=project_id,
            base_path=base_path,
            status="failed",
            progress=0,
            error=str(exc),
            db=db,
            redis_client=redis_client,
        )
        raise
