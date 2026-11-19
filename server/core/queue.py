"""ARQ Queue Manager & Job Dispatching Interface (TASK-4.1)."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import arq
from arq.connections import ArqRedis, RedisSettings

from server.core.config import get_settings
from workers.config import get_redis_settings

logger = logging.getLogger(__name__)

_arq_pool: Optional[ArqRedis] = None


async def get_arq_pool(redis_settings: Optional[RedisSettings] = None) -> ArqRedis:
    """Obtain or initialize global ARQ Redis connection pool."""
    global _arq_pool
    if _arq_pool is None:
        settings = redis_settings or get_redis_settings()
        _arq_pool = await arq.create_pool(settings)
    return _arq_pool


async def close_arq_pool() -> None:
    """Close active ARQ Redis connection pool."""
    global _arq_pool
    if _arq_pool is not None:
        await _arq_pool.close()
        _arq_pool = None


class QueueManager:
    """Typed job dispatcher for CineForge 7-Stage Video Pipeline."""

    def __init__(self, pool: Optional[ArqRedis] = None) -> None:
        self._pool = pool

    async def _get_pool(self) -> ArqRedis:
        if self._pool is not None:
            return self._pool
        return await get_arq_pool()

    async def enqueue_planner_task(
        self,
        project_id: str,
        user_prompt: str,
        format_type: str = "cinematic_drama",
        aspect_ratio: str = "16:9",
    ) -> str:
        """Enqueue Stage 1: Multimodal Master Manifest Planning."""
        pool = await self._get_pool()
        job = await pool.enqueue_job(
            "task_planner",
            project_id=project_id,
            user_prompt=user_prompt,
            format_type=format_type,
            aspect_ratio=aspect_ratio,
        )
        return str(job.job_id) if job else ""

    async def enqueue_consistency_batch(
        self,
        project_id: str,
        target_ids: Optional[List[str]] = None,
    ) -> List[str]:
        """Enqueue Stage 2: 360° Character & Object consistency generation batch."""
        pool = await self._get_pool()
        job = await pool.enqueue_job(
            "task_consistency_batch",
            project_id=project_id,
            target_ids=target_ids,
        )
        return [str(job.job_id)] if job else []

    async def enqueue_keyframe_batch(
        self,
        project_id: str,
        scene_ids: Optional[List[str]] = None,
    ) -> List[str]:
        """Enqueue Stage 3: Reference-injected anchor keyframes batch."""
        pool = await self._get_pool()
        job = await pool.enqueue_job(
            "task_keyframe_batch",
            project_id=project_id,
            scene_ids=scene_ids,
        )
        return [str(job.job_id)] if job else []

    async def enqueue_audio_merge(
        self,
        project_id: str,
        scene_id: str,
    ) -> str:
        """Enqueue Stage 4: Dialogue/Voiceover synthesis & per-scene FFmpeg audio mixing."""
        pool = await self._get_pool()
        job = await pool.enqueue_job(
            "task_audio_merge",
            project_id=project_id,
            scene_id=scene_id,
        )
        return str(job.job_id) if job else ""

    async def enqueue_video_generation(
        self,
        project_id: str,
        scene_id: str,
    ) -> str:
        """Enqueue Stage 5: Visual scene generation with start/end frames & lip-sync."""
        pool = await self._get_pool()
        job = await pool.enqueue_job(
            "task_video_gen",
            project_id=project_id,
            scene_id=scene_id,
        )
        return str(job.job_id) if job else ""

    async def enqueue_timeline_assembly(
        self,
        project_id: str,
        burn_captions: bool = True,
        export_zip: bool = True,
    ) -> str:
        """Enqueue Stage 6 & 7: Timeline concatenation, audio ducking, subtitle burn & ZIP bundle."""
        pool = await self._get_pool()
        job = await pool.enqueue_job(
            "task_timeline_assembly",
            project_id=project_id,
            burn_captions=burn_captions,
            export_zip=export_zip,
        )
        return str(job.job_id) if job else ""

    async def get_job_info(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Query ARQ Redis for ephemeral job metadata and execution state."""
        pool = await self._get_pool()
        job = arq.jobs.Job(job_id=job_id, redis=pool)
        status = await job.status()
        info = await job.info()
        return {
            "job_id": job_id,
            "status": status.value if hasattr(status, "value") else str(status),
            "function": info.function if info else None,
            "enqueue_time": info.enqueue_time.isoformat() if info and info.enqueue_time else None,
            "success": info.success if info else None,
        }
