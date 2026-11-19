"""Stage 4: Multi-Track Audio Synthesis & Per-Scene FFmpeg Mix (TASK-6.4)."""

from __future__ import annotations

import asyncio
import logging
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.core.media.audio_mixer import AudioMixer, AudioTrackInput
from server.core.storage import get_storage_service
from server.models.project import Project
from server.providers.audio import get_tts_provider
from workers.utils.manifest_updater import update_node_status

logger = logging.getLogger(__name__)


async def generate_audio_batch(
    project_id: str,
    db: AsyncSession,
    scene_ids: Optional[List[str]] = None,
) -> Project:
    """Batch-synthesize dialogue & voiceover and composite per-scene master audio tracks."""
    stmt = select(Project).where(Project.id == project_id)
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()
    if not project:
        raise ValueError(f"Project '{project_id}' not found.")

    manifest = project.manifest or {}
    scenes = manifest.get("scenes", [])
    tts_provider = get_tts_provider()
    storage = get_storage_service()
    mixer = AudioMixer()

    semaphore = asyncio.Semaphore(5)
    db_lock = asyncio.Lock()

    async def _process_scene_audio(index: int, scene: Dict[str, Any]) -> None:
        scene_id = scene.get("id", f"scene_{index + 1:02d}")
        if scene_ids and scene_id not in scene_ids:
            return

        base_path = f"/scenes/{index}/audio"
        audio_cfg = scene.get("audio", {})
        ts = scene.get("timestamp", {})
        scene_duration = float(ts.get("endSec", 5.0) - ts.get("startSec", 0.0))
        if scene_duration <= 0:
            scene_duration = 5.0

        async with semaphore:
            async with db_lock:
                await update_node_status(
                    project_id=project_id,
                    base_path=base_path,
                    status="generating",
                    progress=20,
                    db=db,
                )

            try:
                tracks_to_mix: List[AudioTrackInput] = []

                with tempfile.TemporaryDirectory(prefix="audio_mix_") as tmp_dir:
                    tmp_path = Path(tmp_dir)

                    # 1. Synthesize Voiceover if enabled
                    vo_cfg = audio_cfg.get("voiceover")
                    if vo_cfg and vo_cfg.get("enabled") and vo_cfg.get("text"):
                        vo_res = await tts_provider.synthesize_speech(
                            text=vo_cfg["text"],
                            project_id=project_id,
                            scene_id=scene_id,
                            speaker_id="narrator",
                            voice_id=vo_cfg.get("voiceId"),
                        )
                        # Download VO audio locally for mixing
                        vo_file = tmp_path / "vo.m4a"
                        await storage.download_asset_to_file(vo_res.audio_url, vo_file)

                        tracks_to_mix.append(
                            AudioTrackInput(
                                file_path=vo_file,
                                offset_sec=float(vo_cfg.get("startOffsetSec", 0.0)),
                                label="voiceover",
                            )
                        )

                    # 2. Synthesize Dialogue Lines
                    dialogue_lines = audio_cfg.get("dialogue", [])
                    for d_idx, dlg in enumerate(dialogue_lines):
                        if dlg.get("text"):
                            dlg_res = await tts_provider.synthesize_speech(
                                text=dlg["text"],
                                project_id=project_id,
                                scene_id=scene_id,
                                speaker_id=dlg.get("speakerId", "char_01"),
                                voice_id=dlg.get("voiceId"),
                            )
                            dlg_file = tmp_path / f"dlg_{d_idx}.m4a"
                            await storage.download_asset_to_file(dlg_res.audio_url, dlg_file)

                            tracks_to_mix.append(
                                AudioTrackInput(
                                    file_path=dlg_file,
                                    offset_sec=float(dlg.get("startOffsetSec", 0.0)),
                                    label=f"dlg_{d_idx}",
                                )
                            )

                    # 3. Mix Tracks using FFmpeg filtergraph
                    scene_master_file = tmp_path / "scene_master.m4a"
                    mixer.mix_scene_audio(
                        tracks=tracks_to_mix,
                        scene_duration_sec=scene_duration,
                        output_path=scene_master_file,
                    )

                    # 4. Upload merged audio track to S3
                    persist_res = await storage.upload_file(
                        file_path=scene_master_file,
                        project_id=project_id,
                        subfolder=f"scenes/{scene_id}/audio",
                        extension="m4a",
                    )

                # 5. Update manifest node
                from server.core.patch_engine import create_replace_patch
                patches = [
                    create_replace_patch(f"{base_path}/status", "completed"),
                    create_replace_patch(f"{base_path}/mergedSceneAudioUrl", persist_res.public_url),
                ]
                from workers.utils.manifest_updater import update_manifest_patches
                async with db_lock:
                    await update_manifest_patches(
                        project_id=project_id,
                        patches=patches,
                        db=db,
                    )

            except Exception as exc:
                logger.exception("Failed audio synthesis/mixing for scene %s: %s", scene_id, exc)
                async with db_lock:
                    await update_node_status(
                        project_id=project_id,
                        base_path=base_path,
                        status="failed",
                        progress=0,
                        error=str(exc),
                        db=db,
                    )

    tasks = [_process_scene_audio(i, s) for i, s in enumerate(scenes)]
    await asyncio.gather(*tasks)

    await db.refresh(project)
    return project
