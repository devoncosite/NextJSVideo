"""Tests for ARQ Worker Settings & Queue Manager (TASK-4.1)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
import pytest

from server.core.queue import QueueManager
from workers.config import get_redis_settings
from workers.worker import WorkerSettings


def test_redis_settings_parser() -> None:
    redis_settings = get_redis_settings()
    assert redis_settings.host in ("127.0.0.1", "localhost")
    assert redis_settings.port == 6379


def test_worker_settings_functions() -> None:
    funcs = [f.__name__ for f in WorkerSettings.functions]
    assert "task_planner" in funcs
    assert "task_consistency_batch" in funcs
    assert "task_keyframe_batch" in funcs
    assert "task_audio_merge" in funcs
    assert "task_video_gen" in funcs
    assert "task_timeline_assembly" in funcs


@pytest.mark.asyncio
async def test_queue_manager_dispatch_jobs() -> None:
    mock_pool = MagicMock()
    mock_job = MagicMock()
    mock_job.job_id = "arq_mock_job_12345"
    mock_pool.enqueue_job = AsyncMock(return_value=mock_job)

    qm = QueueManager(pool=mock_pool)

    # 1. Enqueue planner
    job_id = await qm.enqueue_planner_task("proj_01", "A coastal drone thriller")
    assert job_id == "arq_mock_job_12345"
    mock_pool.enqueue_job.assert_called_with(
        "task_planner",
        project_id="proj_01",
        user_prompt="A coastal drone thriller",
        format_type="cinematic_drama",
        aspect_ratio="16:9",
    )

    # 2. Enqueue consistency batch
    batch_ids = await qm.enqueue_consistency_batch("proj_01", ["char_01", "obj_01"])
    assert batch_ids == ["arq_mock_job_12345"]

    # 3. Enqueue audio merge
    audio_id = await qm.enqueue_audio_merge("proj_01", "scene_01")
    assert audio_id == "arq_mock_job_12345"

    # 4. Enqueue video generation
    vid_id = await qm.enqueue_video_generation("proj_01", "scene_01")
    assert vid_id == "arq_mock_job_12345"

    # 5. Enqueue timeline assembly
    asm_id = await qm.enqueue_timeline_assembly("proj_01", burn_captions=True, export_zip=True)
    assert asm_id == "arq_mock_job_12345"
