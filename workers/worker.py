"""ARQ Worker Entrypoint & Task Implementations (TASK-4.1)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

import redis.asyncio as aioredis
from arq import ArqRedis
from arq.connections import RedisSettings
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from server.core.config import get_settings
from server.core.database import create_db_engine
from server.core.storage import StorageService
from server.models.job import JobStage
from server.pipeline.stage1_planner import select_pitch_and_expand_manifest
from server.pipeline.stage2_consistencies import generate_consistencies_batch
from server.pipeline.stage3_keyframes import generate_keyframes_batch
from server.pipeline.stage4_audio import generate_audio_batch
from server.pipeline.stage5_video import generate_video_batch
from server.pipeline.stage6_assembly import assemble_timeline_pipeline
from server.pipeline.stage7_export import export_project_zip_bundle
from workers.config import (
    DEFAULT_JOB_TIMEOUT_SECONDS,
    KEEP_RESULT_SECONDS,
    MAX_CONCURRENT_JOBS,
    PROVIDER_SEMAPHORE_LIMITS,
    get_redis_settings,
)
from workers.utils.manifest_updater import (
    safe_worker_execution,
    update_manifest_node,
    update_node_status,
)

logger = logging.getLogger(__name__)

# Global concurrency semaphores per external provider
provider_semaphores: Dict[str, asyncio.Semaphore] = {}


async def startup(ctx: Dict[str, Any]) -> None:
    """Initialize shared database engine, Redis pub/sub client, and provider semaphores."""
    settings = get_settings()
    engine = create_db_engine()
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    storage = StorageService(settings=settings)

    ctx["engine"] = engine
    ctx["session_factory"] = session_factory
    ctx["redis_client"] = redis_client
    ctx["storage"] = storage

    for provider, limit in PROVIDER_SEMAPHORE_LIMITS.items():
        provider_semaphores[provider] = asyncio.Semaphore(limit)

    logger.info("ARQ Worker initialized with DB engine and Redis pub/sub connection.")


async def shutdown(ctx: Dict[str, Any]) -> None:
    """Gracefully terminate database pools and Redis connections on SIGINT/SIGTERM."""
    if "redis_client" in ctx and ctx["redis_client"] is not None:
        await ctx["redis_client"].aclose()
    if "engine" in ctx and ctx["engine"] is not None:
        await ctx["engine"].dispose()
    logger.info("ARQ Worker shut down gracefully.")


# --- Worker Task Definitions ---

async def task_planner(
    ctx: Dict[str, Any],
    project_id: str,
    user_prompt: str,
    format_type: str = "cinematic_drama",
    aspect_ratio: str = "16:9",
) -> Dict[str, Any]:
    """Execute Stage 1: Multimodal Master Manifest Planning."""
    session_factory = ctx.get("session_factory")
    redis_client = ctx.get("redis_client")
    job_id = ctx.get("job_id", "planner_job")

    async with session_factory() as db:
        async with safe_worker_execution(
            project_id=project_id,
            base_path="/scenes",
            stage=JobStage.PLANNER,
            target_id="planner",
            arq_job_id=job_id,
            db=db,
            redis_client=redis_client,
        ):
            logger.info("Executing planner for project %s (prompt: %s)", project_id, user_prompt[:40])
            await select_pitch_and_expand_manifest(
                project_id=project_id,
                pitch_index=1,
                user_prompt=user_prompt,
                format_type=format_type,
                db=db,
                aspect_ratio=aspect_ratio,
            )
            return {"project_id": project_id, "status": "completed"}


async def task_consistency_batch(
    ctx: Dict[str, Any],
    project_id: str,
    target_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Execute Stage 2: 360° Character & Object consistency generation batch."""
    session_factory = ctx.get("session_factory")
    redis_client = ctx.get("redis_client")
    job_id = ctx.get("job_id", "consistency_job")

    async with session_factory() as db:
        async with safe_worker_execution(
            project_id=project_id,
            base_path="/consistencies",
            stage=JobStage.CONSISTENCIES,
            target_id="consistencies_batch",
            arq_job_id=job_id,
            db=db,
            redis_client=redis_client,
        ):
            logger.info("Generating consistency batch for project %s", project_id)
            await generate_consistencies_batch(
                project_id=project_id,
                db=db,
                target_ids=target_ids,
            )
            return {"project_id": project_id, "status": "completed"}


async def task_keyframe_batch(
    ctx: Dict[str, Any],
    project_id: str,
    scene_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Execute Stage 3: Reference-injected anchor keyframes batch."""
    session_factory = ctx.get("session_factory")
    redis_client = ctx.get("redis_client")
    job_id = ctx.get("job_id", "keyframe_job")

    async with session_factory() as db:
        async with safe_worker_execution(
            project_id=project_id,
            base_path="/scenes",
            stage=JobStage.KEYFRAMES,
            target_id="keyframe_batch",
            arq_job_id=job_id,
            db=db,
            redis_client=redis_client,
        ):
            logger.info("Generating keyframes batch for project %s", project_id)
            await generate_keyframes_batch(
                project_id=project_id,
                db=db,
                scene_ids=scene_ids,
            )
            return {"project_id": project_id, "status": "completed"}


async def task_audio_merge(
    ctx: Dict[str, Any],
    project_id: str,
    scene_id: str,
) -> Dict[str, Any]:
    """Execute Stage 4: Dialogue/Voiceover synthesis & per-scene FFmpeg audio mixing."""
    session_factory = ctx.get("session_factory")
    redis_client = ctx.get("redis_client")
    job_id = ctx.get("job_id", f"audio_{scene_id}")

    async with session_factory() as db:
        async with safe_worker_execution(
            project_id=project_id,
            base_path=f"/scenes/0/audio",
            stage=JobStage.AUDIO,
            target_id=scene_id,
            arq_job_id=job_id,
            db=db,
            redis_client=redis_client,
        ):
            logger.info("Merging audio for scene %s in project %s", scene_id, project_id)
            await generate_audio_batch(
                project_id=project_id,
                db=db,
                scene_ids=[scene_id] if scene_id else None,
            )
            return {"project_id": project_id, "scene_id": scene_id, "status": "completed"}


async def task_video_gen(
    ctx: Dict[str, Any],
    project_id: str,
    scene_id: str,
) -> Dict[str, Any]:
    """Execute Stage 5: Visual scene generation with start/end frames & lip-sync."""
    session_factory = ctx.get("session_factory")
    redis_client = ctx.get("redis_client")
    job_id = ctx.get("job_id", f"video_{scene_id}")

    async with session_factory() as db:
        async with safe_worker_execution(
            project_id=project_id,
            base_path=f"/scenes/0/video",
            stage=JobStage.VIDEO,
            target_id=scene_id,
            arq_job_id=job_id,
            db=db,
            redis_client=redis_client,
        ):
            logger.info("Generating video for scene %s in project %s", scene_id, project_id)
            await generate_video_batch(
                project_id=project_id,
                db=db,
                scene_ids=[scene_id] if scene_id else None,
            )
            return {"project_id": project_id, "scene_id": scene_id, "status": "completed"}


async def task_timeline_assembly(
    ctx: Dict[str, Any],
    project_id: str,
    burn_captions: bool = True,
    export_zip: bool = True,
) -> Dict[str, Any]:
    """Execute Stage 6 & 7: Timeline concatenation, audio ducking, subtitle burn & ZIP bundle."""
    session_factory = ctx.get("session_factory")
    redis_client = ctx.get("redis_client")
    job_id = ctx.get("job_id", "timeline_assembly")

    async with session_factory() as db:
        async with safe_worker_execution(
            project_id=project_id,
            base_path="/assembly",
            stage=JobStage.ASSEMBLY,
            target_id="assembly",
            arq_job_id=job_id,
            db=db,
            redis_client=redis_client,
        ):
            logger.info("Assembling timeline for project %s (burn_captions=%s)", project_id, burn_captions)
            await assemble_timeline_pipeline(project_id=project_id, db=db)
            if export_zip:
                await export_project_zip_bundle(project_id=project_id, db=db)
            return {"project_id": project_id, "status": "completed"}


class WorkerSettings:
    """ARQ Worker configuration specification."""

    functions = [
        task_planner,
        task_consistency_batch,
        task_keyframe_batch,
        task_audio_merge,
        task_video_gen,
        task_timeline_assembly,
    ]
    redis_settings: RedisSettings = get_redis_settings()
    on_startup = startup
    on_shutdown = shutdown
    max_jobs: int = MAX_CONCURRENT_JOBS
    job_timeout: int = DEFAULT_JOB_TIMEOUT_SECONDS
    keep_result: int = KEEP_RESULT_SECONDS
