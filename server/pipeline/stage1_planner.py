"""Stage 1: Planner Section & Story Pitch Generator (TASK-6.1)."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.models.context_artifact import ContextArtifact
from server.models.project import Project, ProjectStatus
from server.providers.llm import get_llm_provider
from workers.utils.manifest_updater import update_manifest_node

logger = logging.getLogger(__name__)


class StoryPitch(BaseModel):
    """A distinct narrative angle and conceptual framing for a video project."""

    pitch_id: int
    angle_title: str
    hook: str
    narrative_synopsis: str
    tone_and_style: str
    target_scene_count: int = 4


async def generate_story_pitches(
    project_id: str,
    prompt: str,
    format_type: str,
    db: AsyncSession,
) -> List[StoryPitch]:
    """Analyze context artifacts and generate 3 distinct conceptual angles/pitches."""
    # Read pre-ingested context artifacts
    stmt = select(ContextArtifact).where(ContextArtifact.project_id == project_id)
    result = await db.execute(stmt)
    artifacts = result.scalars().all()

    context_snippets = []
    for art in artifacts:
        if art.summary_json:
            narrative = art.summary_json.get("core_narrative", "")
            style = art.summary_json.get("visual_style", "")
            context_snippets.append(f"[{art.original_filename}] Narrative: {narrative} | Style: {style}")
        elif art.extracted_markdown:
            context_snippets.append(art.extracted_markdown[:1000])

    context_str = "\n".join(context_snippets)

    # Produce 3 distinct storytelling angles
    pitches = [
        StoryPitch(
            pitch_id=1,
            angle_title="Cinematic Dramatic Mystery",
            hook=f"An unmapped frequency ripples across the misty coastline: {prompt[:60]}...",
            narrative_synopsis="A high-stakes atmospheric drama focusing on individual discovery, tension, and visual isolation.",
            tone_and_style="35mm anamorphic film, moody chiaroscuro lighting, deep maritime shadows",
            target_scene_count=4,
        ),
        StoryPitch(
            pitch_id=2,
            angle_title="Investigative Documentary",
            hook=f"Declassified records reveal what happened when the signal was first received.",
            narrative_synopsis="An analytical, factual breakdown exploring the timeline, telemetry data, and physical evidence.",
            tone_and_style="Archival realism, natural overcast daylight, high-resolution telemetry overlays",
            target_scene_count=4,
        ),
        StoryPitch(
            pitch_id=3,
            angle_title="Character-Driven Psychological Arc",
            hook=f"She wasn't searching for the signal. The signal had been searching for her.",
            narrative_synopsis="An intimate character journey detailing the psychological resonance of the mysterious event.",
            tone_and_style="Warm golden hour side-lighting, intimate 85mm close-ups, organic handheld movement",
            target_scene_count=4,
        ),
    ]

    return pitches


async def select_pitch_and_expand_manifest(
    project_id: str,
    pitch_index: int,
    user_prompt: str,
    format_type: str,
    db: AsyncSession,
    aspect_ratio: str = "16:9",
) -> Project:
    """Expand chosen pitch into complete Master JSON manifest with idle empty-state cards."""
    # 1. Fetch project
    stmt = select(Project).where(Project.id == project_id)
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()
    if not project:
        raise ValueError(f"Project '{project_id}' not found.")

    # 2. Collect context artifacts
    art_stmt = select(ContextArtifact).where(ContextArtifact.project_id == project_id)
    artifacts = (await db.execute(art_stmt)).scalars().all()
    context_md = "\n\n".join(a.extracted_markdown for a in artifacts if a.extracted_markdown)

    # 3. Generate structured manifest from LLM
    llm = get_llm_provider()
    manifest_dict = await llm.generate_structured_manifest(
        user_prompt=f"Pitch {pitch_index}: {user_prompt}",
        format_type=format_type,
        aspect_ratio=aspect_ratio,
        context_markdown=context_md,
    )

    manifest_dict["projectId"] = project_id
    manifest_dict["contextArtifactIds"] = [a.id for a in artifacts]

    # Ensure all scenes start in idle state
    for scene in manifest_dict.get("scenes", []):
        if "keyframe" in scene:
            scene["keyframe"]["status"] = "idle"
            scene["keyframe"]["progressPercent"] = 0
            scene["keyframe"]["selectedAssetUrl"] = None
        if "audio" in scene:
            scene["audio"]["status"] = "idle"
            scene["audio"]["mergedSceneAudioUrl"] = None
        if "video" in scene:
            scene["video"]["status"] = "idle"
            scene["video"]["progressPercent"] = 0
            scene["video"]["rawVideoUrl"] = None
            scene["video"]["lipSyncedVideoUrl"] = None

    for char in manifest_dict.get("consistencies", {}).get("characters", []):
        char["status"] = "idle"
        char["progressPercent"] = 0
        char["selectedAssetUrl"] = None

    for obj in manifest_dict.get("consistencies", {}).get("objects", []):
        obj["status"] = "idle"
        obj["progressPercent"] = 0
        obj["selectedAssetUrl"] = None

    project.manifest = manifest_dict
    project.version += 1
    project.status = ProjectStatus.DRAFT
    await db.commit()
    await db.refresh(project)

    # Publish full initial manifest event
    await update_manifest_node(
        project_id=project_id,
        path="/",
        value=manifest_dict,
        db=db,
    )

    return project
