"""Stage 2: Characters & Objects Batch Engine with Turnarounds (TASK-6.2)."""

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


async def generate_consistencies_batch(
    project_id: str,
    db: AsyncSession,
    target_ids: Optional[List[str]] = None,
) -> Project:
    """Generate 360° character model sheets and multi-angle product turnaround sheets."""
    stmt = select(Project).where(Project.id == project_id)
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()
    if not project:
        raise ValueError(f"Project '{project_id}' not found.")

    manifest = project.manifest or {}
    consistencies = manifest.get("consistencies", {})
    characters = consistencies.get("characters", [])
    objects = consistencies.get("objects", [])

    image_provider = get_image_provider()
    semaphore = asyncio.Semaphore(5)
    db_lock = asyncio.Lock()

    async def _process_character(index: int, char: Dict[str, Any]) -> None:
        char_id = char.get("id", f"char_{index:02d}")
        if target_ids and char_id not in target_ids:
            return

        base_path = f"/consistencies/characters/{index}"
        prompt = char.get("prompt360", f"Character turnaround sheet of {char.get('name', 'character')}")

        # Ensure turnaround specifications are present
        if "turnaround" not in prompt.lower():
            prompt += ", 360-degree character turnaround sheet, front view, side profile, back view, neutral studio lighting"

        async with semaphore:
            # 1. Flip to generating
            async with db_lock:
                await update_node_status(
                    project_id=project_id,
                    base_path=base_path,
                    status="generating",
                    progress=25,
                    db=db,
                )

            try:
                # 2. Generate 4 candidate variants
                res = await image_provider.generate_image(
                    prompt=prompt,
                    project_id=project_id,
                    subfolder="chars",
                    aspect_ratio="16:9",
                    num_variants=4,
                )

                # 3. Mark completed with selected asset and variants
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
                logger.exception("Failed generating character %s: %s", char_id, exc)
                async with db_lock:
                    await update_node_status(
                        project_id=project_id,
                        base_path=base_path,
                        status="failed",
                        progress=0,
                        error=str(exc),
                        db=db,
                    )

    async def _process_object(index: int, obj: Dict[str, Any]) -> None:
        obj_id = obj.get("id", f"obj_{index:02d}")
        if target_ids and obj_id not in target_ids:
            return

        base_path = f"/consistencies/objects/{index}"
        prompt = obj.get("prompt360", f"Multi-angle product showcase of {obj.get('name', 'object')}")

        if "showcase" not in prompt.lower() and "turnaround" not in prompt.lower():
            prompt += ", multi-angle product showcase sheet, clean studio gradient background, soft fill lighting"

        async with semaphore:
            async with db_lock:
                await update_node_status(
                    project_id=project_id,
                    base_path=base_path,
                    status="generating",
                    progress=25,
                    db=db,
                )

            try:
                res = await image_provider.generate_image(
                    prompt=prompt,
                    project_id=project_id,
                    subfolder="objects",
                    aspect_ratio="16:9",
                    num_variants=4,
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
                logger.exception("Failed generating object %s: %s", obj_id, exc)
                async with db_lock:
                    await update_node_status(
                        project_id=project_id,
                        base_path=base_path,
                        status="failed",
                        progress=0,
                        error=str(exc),
                        db=db,
                    )

    tasks = [
        _process_character(i, c) for i, c in enumerate(characters)
    ] + [
        _process_object(i, o) for i, o in enumerate(objects)
    ]

    await asyncio.gather(*tasks)

    await db.refresh(project)
    return project
