"""Stage 7: Export Presets & Full Project ZIP Packager (TASK-6.7)."""

from __future__ import annotations

import json
import logging
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.core.media.assembler import (
    generate_ass_subtitles,
    generate_srt_subtitles,
    transcode_preset,
)
from server.core.patch_engine import create_replace_patch
from server.core.storage import get_storage_service
from server.models.project import Project
from workers.utils.manifest_updater import update_manifest_patches, update_node_status

logger = logging.getLogger(__name__)


async def export_project_zip_bundle(
    project_id: str,
    db: AsyncSession,
    include_presets: bool = True,
) -> Project:
    """Package complete project manifest, media assets, subtitles, and transcode variants into a ZIP archive."""
    stmt = select(Project).where(Project.id == project_id)
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()
    if not project:
        raise ValueError(f"Project '{project_id}' not found.")

    manifest = project.manifest or {}
    storage = get_storage_service()

    base_path = "/assembly"

    try:
        with tempfile.TemporaryDirectory(prefix="export_zip_") as tmp_dir:
            tmp_path = Path(tmp_dir)
            bundle_dir = tmp_path / f"cineforge_{project_id}"
            bundle_dir.mkdir(parents=True, exist_ok=True)

            chars_dir = bundle_dir / "characters"
            chars_dir.mkdir(exist_ok=True)
            objs_dir = bundle_dir / "objects"
            objs_dir.mkdir(exist_ok=True)
            kfs_dir = bundle_dir / "keyframes"
            kfs_dir.mkdir(exist_ok=True)
            audio_dir = bundle_dir / "audio"
            audio_dir.mkdir(exist_ok=True)
            scenes_dir = bundle_dir / "scenes"
            scenes_dir.mkdir(exist_ok=True)
            exports_dir = bundle_dir / "exports"
            exports_dir.mkdir(exist_ok=True)

            # 1. Write project.json Master Manifest
            manifest_file = bundle_dir / "project.json"
            manifest_file.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

            # 2. Extract dialogue for subtitles
            scenes = manifest.get("scenes", [])
            dialogue_events: List[Dict[str, Any]] = []
            cumulative_time = 0.0

            for scene in scenes:
                ts = scene.get("timestamp", {})
                duration = float(ts.get("endSec", 5.0) - ts.get("startSec", 0.0))
                aud = scene.get("audio", {})
                vo = aud.get("voiceover", {})
                if vo and vo.get("enabled") and vo.get("text"):
                    vo_start_off = float(vo.get("startOffsetSec", 0.0))
                    vo_end_off = float(vo.get("endOffsetSec", vo_start_off + 2.5))
                    dialogue_events.append({
                        "start": cumulative_time + vo_start_off,
                        "end": cumulative_time + vo_end_off,
                        "text": vo["text"],
                    })
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

            generate_ass_subtitles(dialogue_events, bundle_dir / "subtitles.ass")
            generate_srt_subtitles(dialogue_events, bundle_dir / "subtitles.srt")

            # 3. Download referenced media assets
            # Characters
            chars = manifest.get("consistencies", {}).get("characters", [])
            for idx, c in enumerate(chars):
                c_id = c.get("id", f"char_{idx:02d}")
                url = c.get("selectedAssetUrl")
                if url:
                    await storage.download_asset_to_file(url, chars_dir / f"{c_id}.png")

            # Objects
            objs = manifest.get("consistencies", {}).get("objects", [])
            for idx, o in enumerate(objs):
                o_id = o.get("id", f"obj_{idx:02d}")
                url = o.get("selectedAssetUrl")
                if url:
                    await storage.download_asset_to_file(url, objs_dir / f"{o_id}.png")

            # Keyframes, Audio, Scene Videos
            for idx, s in enumerate(scenes):
                s_id = s.get("id", f"scene_{idx + 1:02d}")

                # Keyframe
                kf_url = s.get("keyframe", {}).get("selectedAssetUrl")
                if kf_url:
                    await storage.download_asset_to_file(kf_url, kfs_dir / f"{s_id}_keyframe.png")

                # Audio
                aud_url = s.get("audio", {}).get("mergedSceneAudioUrl")
                if aud_url:
                    await storage.download_asset_to_file(aud_url, audio_dir / f"{s_id}_master.m4a")

                # Video
                vid_url = s.get("video", {}).get("lipSyncedVideoUrl") or s.get("video", {}).get("rawVideoUrl")
                if vid_url:
                    await storage.download_asset_to_file(vid_url, scenes_dir / f"{s_id}.mp4")

            # Final Master Video
            final_vid_url = manifest.get("assembly", {}).get("finalVideoUrl")
            local_master = bundle_dir / "final_master.mp4"
            if final_vid_url:
                await storage.download_asset_to_file(final_vid_url, local_master)

                # If local_master exists and include_presets is True, generate presets
                if local_master.exists() and local_master.stat().st_size > 0 and include_presets:
                    try:
                        transcode_preset(
                            input_video=local_master,
                            preset="web_master",
                            output_path=exports_dir / "master_web_1080p.mp4",
                        )
                        transcode_preset(
                            input_video=local_master,
                            preset="vertical_social",
                            output_path=exports_dir / "master_vertical_9_16.mp4",
                        )
                    except Exception as exc:
                        logger.warning("Failed generating transcoding presets: %s", exc)

            # 4. Create ZIP archive
            zip_file_path = tmp_path / f"cineforge_bundle_{project_id}.zip"
            with zipfile.ZipFile(zip_file_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for file_path in bundle_dir.rglob("*"):
                    if file_path.is_file():
                        arcname = file_path.relative_to(bundle_dir)
                        zf.write(file_path, arcname=arcname)

            # 5. Upload ZIP to S3
            persist_res = await storage.upload_file(
                file_path=zip_file_path,
                project_id=project_id,
                subfolder="exports",
                extension="zip",
            )

        # 6. Update manifest node
        patches = [
            create_replace_patch(f"{base_path}/bundleZipUrl", persist_res.public_url),
        ]
        await update_manifest_patches(project_id=project_id, patches=patches, db=db)
        await db.refresh(project)

        return project

    except Exception as exc:
        logger.exception("Failed to create ZIP bundle for project %s: %s", project_id, exc)
        raise
