"""Worker Process Crash Recovery & Orphan Task Reaper (TASK-8.2)."""

from __future__ import annotations

import logging
from typing import Any, List, Optional

import redis.asyncio as aioredis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.models.job import JobQueueRecord, JobStatus

logger = logging.getLogger(__name__)


async def record_task_heartbeat(
    redis_client: Optional[aioredis.Redis],
    arq_job_id: str,
    ttl_seconds: int = 30,
) -> None:
    """Record worker task heartbeat in Redis with short expiration."""
    if redis_client is not None and arq_job_id:
        try:
            await redis_client.set(f"job:{arq_job_id}:heartbeat", "1", ex=ttl_seconds)
        except Exception as exc:
            logger.warning("Failed to record task heartbeat for %s: %s", arq_job_id, exc)


async def clear_task_heartbeat(
    redis_client: Optional[aioredis.Redis],
    arq_job_id: str,
) -> None:
    """Clear active task heartbeat in Redis upon task completion."""
    if redis_client is not None and arq_job_id:
        try:
            await redis_client.delete(f"job:{arq_job_id}:heartbeat")
        except Exception as exc:
            logger.warning("Failed to clear task heartbeat for %s: %s", arq_job_id, exc)


async def recover_orphaned_tasks(
    db: AsyncSession,
    redis_client: Optional[aioredis.Redis] = None,
    max_retries: int = 3,
) -> List[JobQueueRecord]:
    """Scan database for RUNNING jobs missing active heartbeats and requeue or fail them."""
    stmt = select(JobQueueRecord).where(JobQueueRecord.status == JobStatus.RUNNING)
    result = await db.execute(stmt)
    running_jobs = list(result.scalars().all())

    recovered_jobs: List[JobQueueRecord] = []

    for job in running_jobs:
        has_heartbeat = False
        if redis_client is not None and job.arq_job_id:
            try:
                hb = await redis_client.get(f"job:{job.arq_job_id}:heartbeat")
                if hb is not None:
                    has_heartbeat = True
            except Exception as exc:
                logger.warning("Error checking heartbeat for job %s: %s", job.arq_job_id, exc)

        if not has_heartbeat:
            logger.warning(
                "Orphaned task detected: job %s (stage: %s, arq_id: %s) lost heartbeat.",
                job.id,
                job.stage,
                job.arq_job_id,
            )
            if job.retry_count < max_retries:
                job.retry_count += 1
                job.status = JobStatus.QUEUED
                job.error_message = (
                    f"Task recovered from worker crash; requeued (attempt {job.retry_count}/{max_retries})"
                )
            else:
                job.status = JobStatus.FAILED
                job.error_message = (
                    f"Task failed: interrupted by worker crash or lost heartbeat (exceeded {max_retries} retries)"
                )

            recovered_jobs.append(job)

    if recovered_jobs:
        await db.commit()
        for j in recovered_jobs:
            await db.refresh(j)

    return recovered_jobs
