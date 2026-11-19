"""Stage 5: Visual Video Generation & Conditional Lip-Sync Routing (TASK-6.5)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.core.patch_engine import create_replace_patch
from server.models.project import Project
from server.providers.lipsync import get_lipsync_provider
from server.providers.video import get_video_provider
from workers.utils.manifest_updater import update_manifest_patches, update_node_status

logger = logging.getLogger(__name__)


async def generate_video_batch(
    project_id: str,
    db: AsyncSession,
    scene_ids: Optional[List[str]] = None,
) -> Project:
    """Generate image-to-video clips with start/end frame chaining and conditional lip-syncing."""
    stmt = select(Project).where(Project.id == project_id)
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()
    if not project:
        raise ValueError(f"Project '{project_id}' not found.")

    manifest = project.manifest or {}
    scenes = manifest.get("scenes", [])
    outro_frame = manifest.get("outroEndFrame", {})
    global_style = manifest.get("globalStyle", {})
    aspect_ratio = global_style.get("aspectRatio", "16:9")

    video_provider = get_video_provider()
    lipsync_provider = get_lipsync_provider()
    semaphore = asyncio.Semaphore(5)
    db_lock = asyncio.Lock()

    async def _process_scene_video(index: int, scene: Dict[str, Any]) -> None:
        scene_id = scene.get("id", f"scene_{index + 1:02d}")
        if scene_ids and scene_id not in scene_ids:
            return

        base_path = f"/scenes/{index}/video"
        video_cfg = scene.get("video", {})
        keyframe_cfg = scene.get("keyframe", {})
        audio_cfg = scene.get("audio", {})

        # Start frame from current scene keyframe
        start_image = keyframe_cfg.get("selectedAssetUrl") or "http://placeholder/kf_start.png"

        # End frame chaining: next scene's keyframe or outro end frame
        if index + 1 < len(scenes):
            end_image = scenes[index + 1].get("keyframe", {}).get("selectedAssetUrl")
        else:
            end_image = outro_frame.get("selectedAssetUrl")

        ts = scene.get("timestamp", {})
        duration = float(ts.get("endSec", 5.0) - ts.get("startSec", 0.0))
        if duration <= 0:
            duration = 5.0

        motion_prompt = video_cfg.get("motionPrompt", "Cinematic camera movement")

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
                # 1. Generate Raw Video
                vid_res = await video_provider.generate_video(
                    prompt=motion_prompt,
                    project_id=project_id,
                    scene_id=scene_id,
                    start_image_url=start_image,
                    end_image_url=end_image,
                    duration_sec=duration,
                    aspect_ratio=aspect_ratio,
                )

                raw_video_url = vid_res.video_url
                lip_synced_url = raw_video_url

                # 2. Check conditional lip-sync routing
                requires_lipsync = video_cfg.get("requiresLipSync", False)
                supports_native_audio = video_cfg.get("supportsNativeAudio", False)
                merged_audio_url = audio_cfg.get("mergedSceneAudioUrl")

                if requires_lipsync and not supports_native_audio and merged_audio_url:
                    async with db_lock:
                        await update_node_status(
                            project_id=project_id,
                            base_path=base_path,
                            status="generating",
                            progress=70,
                            db=db,
                        )
                    lip_res = await lipsync_provider.apply_lip_sync(
                        video_url=raw_video_url,
                        audio_url=merged_audio_url,
                        project_id=project_id,
                        scene_id=scene_id,
                    )
                    lip_synced_url = lip_res.video_url

                # 3. Update manifest node
                patches = [
                    create_replace_patch(f"{base_path}/status", "completed"),
                    create_replace_patch(f"{base_path}/progressPercent", 100),
                    create_replace_patch(f"{base_path}/rawVideoUrl", raw_video_url),
                    create_replace_patch(f"{base_path}/lipSyncedVideoUrl", lip_synced_url),
                ]
                async with db_lock:
                    await update_manifest_patches(
                        project_id=project_id,
                        patches=patches,
                        db=db,
                    )

            except Exception as exc:
                logger.exception("Failed video generation for scene %s: %s", scene_id, exc)
                async with db_lock:
                    await update_node_status(
                        project_id=project_id,
                        base_path=base_path,
                        status="failed",
                        progress=0,
                        error=str(exc),
                        db=db,
                    )

    tasks = [_process_scene_video(i, s) for i, s in enumerate(scenes)]
    await asyncio.gather(*tasks)

    await db.refresh(project)
    return project
