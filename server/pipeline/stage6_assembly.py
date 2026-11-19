"""Stage 6: Final Video Assembly, Subtitles & Thumbnail Variants (TASK-6.6)."""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.core.media.assembler import TimelineAssembler, generate_ass_subtitles
from server.core.patch_engine import create_replace_patch
from server.core.storage import get_storage_service
from server.models.project import Project, ProjectStatus
from server.providers.image import get_image_provider
from workers.utils.manifest_updater import update_manifest_patches, update_node_status

logger = logging.getLogger(__name__)


async def assemble_timeline_pipeline(
    project_id: str,
    db: AsyncSession,
) -> Project:
    """Concatenate scene videos, mix background audio with ducking, burn subtitles, and generate thumbnails."""
    stmt = select(Project).where(Project.id == project_id)
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()
    if not project:
        raise ValueError(f"Project '{project_id}' not found.")

    manifest = project.manifest or {}
    scenes = manifest.get("scenes", [])
    assembly_cfg = manifest.get("assembly", {})
    burn_captions = assembly_cfg.get("burnCaptions", True)

    storage = get_storage_service()
    assembler = TimelineAssembler()
    image_provider = get_image_provider()

    base_path = "/assembly"
    await update_node_status(
        project_id=project_id,
        base_path=base_path,
        status="generating",
        progress=20,
        db=db,
    )

    try:
        with tempfile.TemporaryDirectory(prefix="assembly_") as tmp_dir:
            tmp_path = Path(tmp_dir)
            video_files: List[Path] = []
            audio_files: List[Path] = []
            dialogue_events: List[Dict[str, Any]] = []

            # 1. Download Scene Videos, Scene Audio, and collect dialogue/VO for subtitles
            cumulative_time = 0.0
            for idx, scene in enumerate(scenes):
                vid = scene.get("video", {})
                aud = scene.get("audio", {})
                ts = scene.get("timestamp", {})
                duration = float(ts.get("endSec", 5.0) - ts.get("startSec", 0.0))

                vid_url = vid.get("lipSyncedVideoUrl") or vid.get("rawVideoUrl")
                if vid_url:
                    v_file = tmp_path / f"scene_{idx:02d}.mp4"
                    await storage.download_asset_to_file(vid_url, v_file)
                    video_files.append(v_file)

                    aud_url = aud.get("mergedSceneAudioUrl")
                    if aud_url:
                        a_file = tmp_path / f"scene_{idx:02d}_audio.m4a"
                        await storage.download_asset_to_file(aud_url, a_file)
                        audio_files.append(a_file)

                    # Collect voiceover for subtitles if enabled
                    vo = aud.get("voiceover", {})
                    if vo and vo.get("enabled") and vo.get("text"):
                        vo_start_off = float(vo.get("startOffsetSec", 0.0))
                        vo_end_off = float(vo.get("endOffsetSec", vo_start_off + 2.5))
                        dialogue_events.append({
                            "start": cumulative_time + vo_start_off,
                            "end": cumulative_time + vo_end_off,
                            "text": vo["text"],
                        })

                    # Collect dialogue for subtitles with cumulative time
                    for dlg in aud.get("dialogue", []):
                        if dlg.get("text"):
                            start_off = float(dlg.get("startOffsetSec", 0.0))
                            end_off = float(dlg.get("endOffsetSec", start_off + 2.0))
                            dialogue_events.append({
                                "start": cumulative_time + start_off,
                                "end": cumulative_time + end_off,
                                "text": dlg["text"],
                            })

                    cumulative_time += duration

            # Download background music if configured
            bgm_file: Optional[Path] = None
            bgm_url = assembly_cfg.get("backgroundMusicUrl")
            if bgm_url:
                bgm_file = tmp_path / "bgm.m4a"
                await storage.download_asset_to_file(bgm_url, bgm_file)

            # 2. Generate .ass subtitle file
            sub_file = tmp_path / "subtitles.ass"
            generate_ass_subtitles(dialogue_events, sub_file)

            # 3. Assemble Timeline
            master_output = tmp_path / "master_1080p.mp4"
            assembler.assemble_timeline(
                scene_video_files=video_files,
                scene_audio_files=audio_files,
                output_path=master_output,
                background_music_file=bgm_file,
                subtitle_file=sub_file,
                burn_captions=burn_captions,
            )

            # 4. Upload Master MP4 to S3
            persist_res = await storage.upload_file(
                file_path=master_output,
                project_id=project_id,
                subfolder="exports",
                extension="mp4",
            )

            # 5. Generate Clickable Thumbnails
            thumb_prompt = assembly_cfg.get("thumbnail", {}).get(
                "prompt", "Dramatic cinematic YouTube video poster thumbnail with vibrant high contrast"
            )
            thumb_res = await image_provider.generate_image(
                prompt=thumb_prompt,
                project_id=project_id,
                subfolder="thumbnails",
                aspect_ratio="16:9",
                num_variants=3,
            )

        # 6. Update manifest and mark project completed
        patches = [
            create_replace_patch(f"{base_path}/status", "completed"),
            create_replace_patch(f"{base_path}/progressPercent", 100),
            create_replace_patch(f"{base_path}/finalVideoUrl", persist_res.public_url),
            create_replace_patch(f"{base_path}/thumbnail/selectedAssetUrl", thumb_res.public_url),
            create_replace_patch(f"{base_path}/thumbnail/variants", thumb_res.variants),
            create_replace_patch(f"{base_path}/thumbnail/status", "completed"),
        ]
        await update_manifest_patches(project_id=project_id, patches=patches, db=db)

        project.status = ProjectStatus.COMPLETED
        await db.commit()
        await db.refresh(project)

        return project

    except Exception as exc:
        logger.exception("Timeline assembly failed for project %s: %s", project_id, exc)
        await update_node_status(
            project_id=project_id,
            base_path=base_path,
            status="failed",
            progress=0,
            error=str(exc),
            db=db,
        )
        raise
