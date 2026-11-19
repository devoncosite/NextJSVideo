"""Intelligent Dependency Invalidation Graph (TASK-8.1)."""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Set, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.core.patch_engine import create_replace_patch
from server.models.project import Project, ProjectStatus
from workers.utils.manifest_updater import update_manifest_patches

logger = logging.getLogger(__name__)


def compute_downstream_invalidations(
    manifest: Dict[str, Any],
    node_path: str,
) -> List[Dict[str, Any]]:
    """Compute RFC 6902 patches that reset downstream dependent pipeline stages to 'idle'."""
    patches: List[Dict[str, Any]] = []
    clean_path = node_path.rstrip("/")

    scenes = manifest.get("scenes", [])
    characters = manifest.get("consistencies", {}).get("characters", [])
    objects = manifest.get("consistencies", {}).get("objects", [])

    # Assembly invalidation helper
    def invalidate_assembly() -> None:
        patches.extend([
            create_replace_patch("/assembly/status", "idle"),
            create_replace_patch("/assembly/progressPercent", 0),
            create_replace_patch("/assembly/finalVideoUrl", None),
            create_replace_patch("/assembly/bundleZipUrl", None),
        ])

    # 1. Invalidation of Character Consistencies
    char_match = re.match(r"^/consistencies/characters/(\d+)", clean_path)
    if char_match:
        c_idx = int(char_match.group(1))
        if 0 <= c_idx < len(characters):
            char_id = characters[c_idx].get("id")
            for s_idx, scene in enumerate(scenes):
                ref_ids = scene.get("keyframe", {}).get("refIds", [])
                if char_id in ref_ids:
                    # Invalidate keyframe and video
                    patches.extend([
                        create_replace_patch(f"/scenes/{s_idx}/keyframe/status", "idle"),
                        create_replace_patch(f"/scenes/{s_idx}/keyframe/progressPercent", 0),
                        create_replace_patch(f"/scenes/{s_idx}/keyframe/selectedAssetUrl", None),
                        create_replace_patch(f"/scenes/{s_idx}/video/status", "idle"),
                        create_replace_patch(f"/scenes/{s_idx}/video/progressPercent", 0),
                        create_replace_patch(f"/scenes/{s_idx}/video/rawVideoUrl", None),
                        create_replace_patch(f"/scenes/{s_idx}/video/lipSyncedVideoUrl", None),
                    ])
            invalidate_assembly()
            return patches

    # 2. Invalidation of Object Consistencies
    obj_match = re.match(r"^/consistencies/objects/(\d+)", clean_path)
    if obj_match:
        o_idx = int(obj_match.group(1))
        if 0 <= o_idx < len(objects):
            obj_id = objects[o_idx].get("id")
            for s_idx, scene in enumerate(scenes):
                ref_ids = scene.get("keyframe", {}).get("refIds", [])
                if obj_id in ref_ids:
                    patches.extend([
                        create_replace_patch(f"/scenes/{s_idx}/keyframe/status", "idle"),
                        create_replace_patch(f"/scenes/{s_idx}/keyframe/progressPercent", 0),
                        create_replace_patch(f"/scenes/{s_idx}/keyframe/selectedAssetUrl", None),
                        create_replace_patch(f"/scenes/{s_idx}/video/status", "idle"),
                        create_replace_patch(f"/scenes/{s_idx}/video/progressPercent", 0),
                        create_replace_patch(f"/scenes/{s_idx}/video/rawVideoUrl", None),
                        create_replace_patch(f"/scenes/{s_idx}/video/lipSyncedVideoUrl", None),
                    ])
            invalidate_assembly()
            return patches

    # 3. Invalidation of Scene Keyframes
    kf_match = re.match(r"^/scenes/(\d+)/keyframe", clean_path)
    if kf_match:
        s_idx = int(kf_match.group(1))
        patches.extend([
            create_replace_patch(f"/scenes/{s_idx}/video/status", "idle"),
            create_replace_patch(f"/scenes/{s_idx}/video/progressPercent", 0),
            create_replace_patch(f"/scenes/{s_idx}/video/rawVideoUrl", None),
            create_replace_patch(f"/scenes/{s_idx}/video/lipSyncedVideoUrl", None),
        ])
        invalidate_assembly()
        return patches

    # 4. Invalidation of Scene Audio
    aud_match = re.match(r"^/scenes/(\d+)/audio", clean_path)
    if aud_match:
        s_idx = int(aud_match.group(1))
        if 0 <= s_idx < len(scenes):
            scene = scenes[s_idx]
            requires_lipsync = scene.get("video", {}).get("requiresLipSync", False)
            if requires_lipsync:
                patches.extend([
                    create_replace_patch(f"/scenes/{s_idx}/video/status", "idle"),
                    create_replace_patch(f"/scenes/{s_idx}/video/progressPercent", 0),
                    create_replace_patch(f"/scenes/{s_idx}/video/lipSyncedVideoUrl", None),
                ])
        invalidate_assembly()
        return patches

    # 5. Invalidation of Scene Video
    vid_match = re.match(r"^/scenes/(\d+)/video", clean_path)
    if vid_match:
        invalidate_assembly()
        return patches

    # Default fallback: invalidate assembly
    invalidate_assembly()
    return patches


async def invalidate_manifest_node(
    project_id: str,
    node_path: str,
    db: AsyncSession,
) -> Tuple[Project, List[Dict[str, Any]]]:
    """Execute dependency graph invalidation for a modified manifest node."""
    stmt = select(Project).where(Project.id == project_id)
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()
    if not project:
        raise ValueError(f"Project '{project_id}' not found.")

    manifest = project.manifest or {}
    patches = compute_downstream_invalidations(manifest, node_path)

    if patches:
        await update_manifest_patches(
            project_id=project_id,
            patches=patches,
            db=db,
        )
        if project.status == ProjectStatus.COMPLETED:
            project.status = ProjectStatus.DRAFT
            await db.commit()

        await db.refresh(project)

    return project, patches
