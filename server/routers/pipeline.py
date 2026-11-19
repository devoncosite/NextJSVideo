"""Pipeline API Router for the 7-Stage Video Generation Engine (Phase 6)."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.core.database import get_db
from server.core.queue import QueueManager
from server.models.project import Project
from server.pipeline.stage1_planner import (
    StoryPitch,
    generate_story_pitches,
    select_pitch_and_expand_manifest,
)
from server.pipeline.stage2_consistencies import generate_consistencies_batch
from server.pipeline.stage3_keyframes import generate_keyframes_batch
from server.pipeline.stage4_audio import generate_audio_batch
from server.pipeline.stage5_video import generate_video_batch
from server.pipeline.stage6_assembly import assemble_timeline_pipeline
from server.pipeline.stage7_export import export_project_zip_bundle

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/projects/{project_id}/pipeline", tags=["pipeline"])


# Request / Response Schemas
class PitchRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    format_type: str = Field(default="cinematic_drama")


class PlannerSelectRequest(BaseModel):
    pitch_index: int = Field(default=1, ge=1, le=3)
    user_prompt: str = Field(..., min_length=1)
    format_type: str = Field(default="cinematic_drama")
    aspect_ratio: str = Field(default="16:9")
    run_async: bool = False


class ConsistenciesRequest(BaseModel):
    target_ids: Optional[List[str]] = None
    run_async: bool = False


class KeyframesRequest(BaseModel):
    scene_ids: Optional[List[str]] = None
    run_async: bool = False


class AudioRequest(BaseModel):
    scene_ids: Optional[List[str]] = None
    run_async: bool = False


class VideoRequest(BaseModel):
    scene_ids: Optional[List[str]] = None
    run_async: bool = False


class AssemblyRequest(BaseModel):
    burn_captions: bool = True
    run_async: bool = False


class ExportRequest(BaseModel):
    include_presets: bool = True


class JobDispatchResponse(BaseModel):
    job_id: str
    status: str
    stage: str


# Endpoints

@router.post("/pitches", response_model=List[StoryPitch])
async def create_story_pitches(
    project_id: str,
    req: PitchRequest,
    db: AsyncSession = Depends(get_db),
) -> List[StoryPitch]:
    """Stage 1.1: Generate 3 distinct conceptual angles/pitches from user prompt and context artifacts."""
    stmt = select(Project).where(Project.id == project_id)
    result = await db.execute(stmt)
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project '{project_id}' not found")

    return await generate_story_pitches(
        project_id=project_id,
        prompt=req.prompt,
        format_type=req.format_type,
        db=db,
    )


@router.post("/planner")
async def execute_planner_stage(
    project_id: str,
    req: PlannerSelectRequest,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Stage 1.2: Select pitch and expand into full Master Manifest scene nodes with idle cards."""
    if req.run_async:
        qm = QueueManager()
        job_id = await qm.enqueue_planner_task(
            project_id=project_id,
            user_prompt=req.user_prompt,
            format_type=req.format_type,
            aspect_ratio=req.aspect_ratio,
        )
        return JobDispatchResponse(job_id=job_id, status="queued", stage="planner")

    project = await select_pitch_and_expand_manifest(
        project_id=project_id,
        pitch_index=req.pitch_index,
        user_prompt=req.user_prompt,
        format_type=req.format_type,
        aspect_ratio=req.aspect_ratio,
        db=db,
    )
    return {"project_id": project.id, "manifest": project.manifest, "version": project.version}


@router.post("/consistencies")
async def execute_consistencies_stage(
    project_id: str,
    req: ConsistenciesRequest,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Stage 2: Batch-generate 360° character sheets and product turnaround angles."""
    if req.run_async:
        qm = QueueManager()
        job_ids = await qm.enqueue_consistency_batch(
            project_id=project_id,
            target_ids=req.target_ids,
        )
        return JobDispatchResponse(
            job_id=job_ids[0] if job_ids else "",
            status="queued",
            stage="consistencies",
        )

    project = await generate_consistencies_batch(
        project_id=project_id,
        db=db,
        target_ids=req.target_ids,
    )
    return {"project_id": project.id, "manifest": project.manifest}


@router.post("/keyframes")
async def execute_keyframes_stage(
    project_id: str,
    req: KeyframesRequest,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Stage 3: Generate anchor keyframes with locked consistency references and chaining."""
    if req.run_async:
        qm = QueueManager()
        job_ids = await qm.enqueue_keyframe_batch(
            project_id=project_id,
            scene_ids=req.scene_ids,
        )
        return JobDispatchResponse(
            job_id=job_ids[0] if job_ids else "",
            status="queued",
            stage="keyframes",
        )

    project = await generate_keyframes_batch(
        project_id=project_id,
        db=db,
        scene_ids=req.scene_ids,
    )
    return {"project_id": project.id, "manifest": project.manifest}


@router.post("/audio")
async def execute_audio_stage(
    project_id: str,
    req: AudioRequest,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Stage 4: Multi-track dialogue and voiceover synthesis with per-scene FFmpeg mixing."""
    if req.run_async:
        qm = QueueManager()
        job_id = await qm.enqueue_audio_merge(
            project_id=project_id,
            scene_id=req.scene_ids[0] if req.scene_ids else "all",
        )
        return JobDispatchResponse(job_id=job_id, status="queued", stage="audio")

    project = await generate_audio_batch(
        project_id=project_id,
        db=db,
        scene_ids=req.scene_ids,
    )
    return {"project_id": project.id, "manifest": project.manifest}


@router.post("/video")
async def execute_video_stage(
    project_id: str,
    req: VideoRequest,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Stage 5: Visual scene generation with frame chaining and conditional lip-syncing."""
    if req.run_async:
        qm = QueueManager()
        job_id = await qm.enqueue_video_generation(
            project_id=project_id,
            scene_id=req.scene_ids[0] if req.scene_ids else "all",
        )
        return JobDispatchResponse(job_id=job_id, status="queued", stage="video")

    project = await generate_video_batch(
        project_id=project_id,
        db=db,
        scene_ids=req.scene_ids,
    )
    return {"project_id": project.id, "manifest": project.manifest}


@router.post("/assembly")
async def execute_assembly_stage(
    project_id: str,
    req: AssemblyRequest,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Stage 6: Final timeline stitching, ducking, subtitle burning, and YouTube thumbnails."""
    if req.run_async:
        qm = QueueManager()
        job_id = await qm.enqueue_timeline_assembly(
            project_id=project_id,
            burn_captions=req.burn_captions,
            export_zip=False,
        )
        return JobDispatchResponse(job_id=job_id, status="queued", stage="assembly")

    project = await assemble_timeline_pipeline(
        project_id=project_id,
        db=db,
    )
    return {"project_id": project.id, "manifest": project.manifest}


@router.post("/export")
async def execute_export_stage(
    project_id: str,
    req: ExportRequest,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Stage 7: Full project ZIP packaging and multi-format transcoding presets."""
    project = await export_project_zip_bundle(
        project_id=project_id,
        db=db,
        include_presets=req.include_presets,
    )
    bundle_url = project.manifest.get("assembly", {}).get("bundleZipUrl") if project.manifest else None
    return {
        "project_id": project.id,
        "bundleZipUrl": bundle_url,
        "status": "completed",
    }
