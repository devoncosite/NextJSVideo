"""Stage 3: Keyframes with Reference Injection & Frame Chaining (TASK-6.3)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.models.project import Project
from server.providers.image import get_image_provider
from workers.utils.manifest_updater import update_node_status

logger = logging.getLogger(__name__)


async def generate_keyframes_batch(
    project_id: str,
    db: AsyncSession,
    scene_ids: Optional[List[str]] = None,
) -> Project:
    """Generate anchor keyframes for all scenes with character/object reference conditioning."""
    stmt = select(Project).where(Project.id == project_id)
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()
    if not project:
        raise ValueError(f"Project '{project_id}' not found.")

    manifest = project.manifest or {}
    consistencies = manifest.get("consistencies", {})
    characters = consistencies.get("characters", [])
    objects = consistencies.get("objects", [])
    scenes = manifest.get("scenes", [])
    outro_frame = manifest.get("outroEndFrame", {})

    # Build asset lookup table: ID -> selectedAssetUrl
    asset_lookup: Dict[str, str] = {}
    for c in characters:
        if c.get("id") and c.get("selectedAssetUrl"):
            asset_lookup[c["id"]] = c["selectedAssetUrl"]
    for o in objects:
        if o.get("id") and o.get("selectedAssetUrl"):
            asset_lookup[o["id"]] = o["selectedAssetUrl"]

    image_provider = get_image_provider()
    semaphore = asyncio.Semaphore(5)
    db_lock = asyncio.Lock()

    async def _process_keyframe(index: int, scene: Dict[str, Any]) -> None:
        scene_id = scene.get("id", f"scene_{index + 1:02d}")
        if scene_ids and scene_id not in scene_ids:
            return

        keyframe = scene.get("keyframe", {})
        base_path = f"/scenes/{index}/keyframe"
        prompt = keyframe.get("prompt", f"Cinematic keyframe for scene {index + 1}")
        ref_ids = keyframe.get("refIds", [])

        # Collect reference image URLs for this scene
        ref_urls: List[str] = [asset_lookup[r_id] for r_id in ref_ids if r_id in asset_lookup]

        async with semaphore:
            async with db_lock:
                await update_node_status(
                    project_id=project_id,
                    base_path=base_path,
                    status="generating",
                    progress=30,
                    db=db,
                )

            try:
                res = await image_provider.generate_image(
                    prompt=prompt,
                    project_id=project_id,
                    subfolder=f"keyframes/{scene_id}",
                    aspect_ratio="16:9",
                    reference_image_urls=ref_urls,
                    image_prompt_strength=0.7,
                    num_variants=2,
                )

                async with db_lock:
                    await update_node_status(
                        project_id=project_id,
                        base_path=base_path,
                        status="completed",
                        progress=100,
                        asset_url=res.public_url,
                        variants=res.variants,
                        db=db,
                    )
            except Exception as exc:
                logger.exception("Failed generating keyframe for scene %s: %s", scene_id, exc)
                async with db_lock:
                    await update_node_status(
                        project_id=project_id,
                        base_path=base_path,
                        status="failed",
                        progress=0,
                        error=str(exc),
                        db=db,
                    )

    # 1. Process scene keyframes in parallel
    scene_tasks = [_process_keyframe(i, s) for i, s in enumerate(scenes)]
    await asyncio.gather(*scene_tasks)

    # 2. Generate Outro End Frame for closing continuity if present
    if outro_frame and outro_frame.get("prompt"):
        outro_prompt = outro_frame.get("prompt", "Cinematic closing frame at dusk")
        try:
            outro_res = await image_provider.generate_image(
                prompt=outro_prompt,
                project_id=project_id,
                subfolder="keyframes/outro",
                aspect_ratio="16:9",
                num_variants=1,
            )
            async with db_lock:
                await update_node_status(
                    project_id=project_id,
                    base_path="/outroEndFrame",
                    status="completed",
                    progress=100,
                    asset_url=outro_res.public_url,
                    variants=outro_res.variants,
                    db=db,
                )
        except Exception as exc:
            logger.warning("Failed generating outro end frame: %s", exc)

    await db.refresh(project)
    return project
