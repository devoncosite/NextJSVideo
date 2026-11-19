"""Comprehensive Tests for the 7-Stage Video Generation Pipeline (Phase 6)."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import json
from pathlib import Path
import subprocess
import tempfile
from typing import Any, AsyncIterator, Dict, Optional
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from server.core.database import get_db_session
from server.core.media.assembler import (
    TimelineAssembler,
    generate_ass_subtitles,
    generate_srt_subtitles,
    transcode_preset,
)
from server.core.media.audio_mixer import AudioMixer, AudioTrackInput
from server.core.storage import StorageService, set_storage_service
from server.main import app
from server.models import Base
from server.models.project import Project, ProjectStatus
from server.schemas.manifest import ProjectFormat
from server.models.user import User
from server.pipeline.stage1_planner import generate_story_pitches, select_pitch_and_expand_manifest
from server.pipeline.stage2_consistencies import generate_consistencies_batch
from server.pipeline.stage3_keyframes import generate_keyframes_batch
from server.pipeline.stage4_audio import generate_audio_batch
from server.pipeline.stage5_video import generate_video_batch
from server.pipeline.stage6_assembly import assemble_timeline_pipeline
from server.pipeline.stage7_export import export_project_zip_bundle
from server.routers.context import DEFAULT_USER_ID, ensure_default_user_exists


class InMemoryMinIOBucket:
    """Mock storage capturing uploads in memory for test isolation."""

    def __init__(self) -> None:
        self.objects: Dict[str, bytes] = {}

    async def upload_file(
        self,
        file_path: str,
        bucket: str,
        object_key: str,
        ExtraArgs: Optional[Dict[str, Any]] = None,
    ) -> None:
        data = Path(file_path).read_bytes()
        self.objects[f"{bucket}/{object_key}"] = data

    async def put_object(
        self,
        Bucket: str,
        Key: str,
        Body: bytes,
        ContentType: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        self.objects[f"{Bucket}/{Key}"] = Body


@pytest.fixture
async def pipeline_test_db():
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    @event.listens_for(test_engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        await ensure_default_user_exists(session)

    yield session_factory
    await test_engine.dispose()


@pytest.fixture(autouse=True)
def setup_mock_storage():
    bucket = InMemoryMinIOBucket()

    @asynccontextmanager
    async def s3_factory():
        yield bucket

    storage = StorageService(s3_client_factory=s3_factory)
    set_storage_service(storage)
    yield storage
    set_storage_service(None)


@pytest.mark.asyncio
async def test_stage1_planner_pitches_and_expansion(pipeline_test_db) -> None:
    """Verify Stage 1: Generate 3 story pitches and expand chosen pitch into full manifest."""
    async with pipeline_test_db() as db:
        # Create initial project
        project = Project(
            id="proj_stage1_test",
            user_id=DEFAULT_USER_ID,
            title="The Signal Deep",
            format="cinematic_drama",
            version=1,
            status=ProjectStatus.DRAFT,
            manifest={},
        )
        db.add(project)
        await db.commit()

        # 1. Generate Pitches
        pitches = await generate_story_pitches(
            project_id=project.id,
            prompt="A mysterious radio signal on the misty Oregon coastline",
            format_type="cinematic_drama",
            db=db,
        )
        assert len(pitches) == 3
        assert pitches[0].pitch_id == 1
        assert "coastline" in pitches[0].hook.lower()

        # 2. Select Pitch 1 and expand manifest
        expanded_project = await select_pitch_and_expand_manifest(
            project_id=project.id,
            pitch_index=1,
            user_prompt="Coastline mystery signal",
            format_type="cinematic_drama",
            db=db,
        )

        manifest = expanded_project.manifest
        assert manifest is not None
        assert "scenes" in manifest
        assert len(manifest["scenes"]) >= 2
        assert "consistencies" in manifest
        assert len(manifest["consistencies"]["characters"]) >= 1

        # Check empty-state cards start idle
        for s in manifest["scenes"]:
            assert s["keyframe"]["status"] == "idle"
            assert s["audio"]["status"] == "idle"
            assert s["video"]["status"] == "idle"


@pytest.mark.asyncio
async def test_stage2_consistencies_batch(pipeline_test_db) -> None:
    """Verify Stage 2: Batch generation of 360° turnaround sheets."""
    async with pipeline_test_db() as db:
        manifest = {
            "projectId": "proj_stage2_test",
            "version": 1,
            "consistencies": {
                "characters": [
                    {
                        "id": "char_01",
                        "name": "Dr. Elena Vance",
                        "prompt360": "Elena Vance, radio astronomer in field jacket",
                        "status": "idle",
                        "selectedAssetUrl": None,
                        "variants": [],
                    }
                ],
                "objects": [
                    {
                        "id": "obj_01",
                        "name": "Field Receiver",
                        "prompt360": "Rugged vintage telemetry transceiver",
                        "status": "idle",
                        "selectedAssetUrl": None,
                        "variants": [],
                    }
                ],
            },
            "scenes": [],
        }
        project = Project(
            id="proj_stage2_test",
            user_id=DEFAULT_USER_ID,
            title="Consistencies Test",
            format="cinematic_drama",
            version=1,
            status=ProjectStatus.DRAFT,
            manifest=manifest,
        )
        db.add(project)
        await db.commit()

        updated_project = await generate_consistencies_batch(
            project_id=project.id,
            db=db,
        )

        chars = updated_project.manifest["consistencies"]["characters"]
        objs = updated_project.manifest["consistencies"]["objects"]

        assert chars[0]["status"] == "completed"
        assert chars[0]["selectedAssetUrl"] is not None
        assert len(chars[0]["variants"]) == 4

        assert objs[0]["status"] == "completed"
        assert objs[0]["selectedAssetUrl"] is not None
        assert len(objs[0]["variants"]) == 4


@pytest.mark.asyncio
async def test_stage3_keyframes_batch(pipeline_test_db) -> None:
    """Verify Stage 3: Keyframe generation with reference injection."""
    async with pipeline_test_db() as db:
        manifest = {
            "projectId": "proj_stage3_test",
            "version": 1,
            "consistencies": {
                "characters": [
                    {
                        "id": "char_01",
                        "name": "Dr. Elena Vance",
                        "status": "completed",
                        "selectedAssetUrl": "mock://storage/chars/elena_turnaround.png",
                        "variants": ["mock://storage/chars/elena_turnaround.png"],
                    }
                ],
                "objects": [],
            },
            "scenes": [
                {
                    "id": "scene_01",
                    "sceneNumber": 1,
                    "timestamp": {"startSec": 0.0, "endSec": 5.0},
                    "keyframe": {
                        "refIds": ["char_01"],
                        "prompt": "Elena Vance standing on the foggy cliff",
                        "status": "idle",
                        "selectedAssetUrl": None,
                        "variants": [],
                    },
                    "audio": {"status": "idle"},
                    "video": {"status": "idle"},
                }
            ],
            "outroEndFrame": {
                "prompt": "Closing view of ocean horizon at dusk",
                "status": "idle",
                "selectedAssetUrl": None,
                "variants": [],
            },
        }
        project = Project(
            id="proj_stage3_test",
            user_id=DEFAULT_USER_ID,
            title="Keyframes Test",
            format="cinematic_drama",
            version=1,
            status=ProjectStatus.DRAFT,
            manifest=manifest,
        )
        db.add(project)
        await db.commit()

        updated_project = await generate_keyframes_batch(
            project_id=project.id,
            db=db,
        )

        scene = updated_project.manifest["scenes"][0]
        assert scene["keyframe"]["status"] == "completed"
        assert scene["keyframe"]["selectedAssetUrl"] is not None

        outro = updated_project.manifest["outroEndFrame"]
        assert outro["status"] == "completed"
        assert outro["selectedAssetUrl"] is not None


@pytest.mark.asyncio
async def test_stage4_audio_synthesis_and_mix(pipeline_test_db, tmp_path) -> None:
    """Verify Stage 4: Dialogue/voiceover synthesis and FFmpeg multi-track mix."""
    # Test FFmpeg mixer unit functionality
    mixer = AudioMixer()

    # Generate synthetic 1-second audio files with lavfi
    a1 = tmp_path / "track1.m4a"
    a2 = tmp_path / "track2.m4a"
    out_audio = tmp_path / "mixed.m4a"

    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=1.0",
        "-c:a", "aac", str(a1)
    ], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=880:duration=1.0",
        "-c:a", "aac", str(a2)
    ], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    tracks = [
        AudioTrackInput(file_path=a1, offset_sec=0.0, label="sine1"),
        AudioTrackInput(file_path=a2, offset_sec=0.5, label="sine2"),
    ]
    mixer.mix_scene_audio(tracks=tracks, scene_duration_sec=2.0, output_path=out_audio)
    assert out_audio.exists()
    assert out_audio.stat().st_size > 0

    # Test pipeline stage execution
    async with pipeline_test_db() as db:
        manifest = {
            "projectId": "proj_stage4_test",
            "version": 1,
            "scenes": [
                {
                    "id": "scene_01",
                    "sceneNumber": 1,
                    "timestamp": {"startSec": 0.0, "endSec": 4.0},
                    "audio": {
                        "voiceover": {
                            "enabled": True,
                            "text": "The signal echoed through the fog.",
                            "startOffsetSec": 0.0,
                            "endOffsetSec": 2.5,
                        },
                        "dialogue": [
                            {
                                "id": "dlg_01",
                                "speakerId": "char_01",
                                "text": "Are you hearing this?",
                                "startOffsetSec": 1.0,
                                "endOffsetSec": 3.0,
                            }
                        ],
                        "status": "idle",
                        "mergedSceneAudioUrl": None,
                    },
                }
            ],
        }
        project = Project(
            id="proj_stage4_test",
            user_id=DEFAULT_USER_ID,
            title="Audio Test",
            format="cinematic_drama",
            version=1,
            status=ProjectStatus.DRAFT,
            manifest=manifest,
        )
        db.add(project)
        await db.commit()

        updated_project = await generate_audio_batch(
            project_id=project.id,
            db=db,
        )

        audio_node = updated_project.manifest["scenes"][0]["audio"]
        assert audio_node["status"] == "completed"
        assert audio_node["mergedSceneAudioUrl"] is not None


@pytest.mark.asyncio
async def test_stage5_video_and_lipsync(pipeline_test_db) -> None:
    """Verify Stage 5: Video generation with conditional lip-sync routing."""
    async with pipeline_test_db() as db:
        manifest = {
            "projectId": "proj_stage5_test",
            "version": 1,
            "globalStyle": {"aspectRatio": "16:9"},
            "scenes": [
                {
                    "id": "scene_01",
                    "sceneNumber": 1,
                    "timestamp": {"startSec": 0.0, "endSec": 5.0},
                    "keyframe": {
                        "selectedAssetUrl": "mock://storage/kf_scene1.png",
                        "status": "completed",
                    },
                    "audio": {
                        "mergedSceneAudioUrl": "mock://storage/audio_scene1.m4a",
                        "status": "completed",
                    },
                    "video": {
                        "motionPrompt": "Slow pan across foggy cliff edge",
                        "requiresLipSync": True,
                        "supportsNativeAudio": False,
                        "status": "idle",
                        "rawVideoUrl": None,
                        "lipSyncedVideoUrl": None,
                    },
                }
            ],
            "outroEndFrame": {"selectedAssetUrl": "mock://storage/outro.png"},
        }
        project = Project(
            id="proj_stage5_test",
            user_id=DEFAULT_USER_ID,
            title="Video Test",
            format="cinematic_drama",
            version=1,
            status=ProjectStatus.DRAFT,
            manifest=manifest,
        )
        db.add(project)
        await db.commit()

        updated_project = await generate_video_batch(
            project_id=project.id,
            db=db,
        )

        vid_node = updated_project.manifest["scenes"][0]["video"]
        assert vid_node["status"] == "completed"
        assert vid_node["rawVideoUrl"] is not None
        assert vid_node["lipSyncedVideoUrl"] is not None


@pytest.mark.asyncio
async def test_stage6_timeline_assembly_and_subtitles(pipeline_test_db, tmp_path) -> None:
    """Verify Stage 6: ASS/SRT subtitles and timeline assembly."""
    # Test subtitle generators
    events = [
        {"start": 0.5, "end": 2.5, "text": "Welcome to CineForge AI."},
        {"start": 3.0, "end": 5.0, "text": "The signal is locked."},
    ]
    ass_file = tmp_path / "test.ass"
    srt_file = tmp_path / "test.srt"
    generate_ass_subtitles(events, ass_file)
    generate_srt_subtitles(events, srt_file)

    assert ass_file.exists()
    assert "[Script Info]" in ass_file.read_text(encoding="utf-8")
    assert srt_file.exists()
    assert "00:00:00,500 --> 00:00:02,500" in srt_file.read_text(encoding="utf-8")

    # Test TimelineAssembler fallback synthetic video
    assembler = TimelineAssembler()
    out_master = tmp_path / "master.mp4"
    assembler.assemble_timeline(
        scene_video_files=[],
        scene_audio_files=[],
        output_path=out_master,
    )
    assert out_master.exists()
    assert out_master.stat().st_size > 0

    # Test full pipeline stage 6
    async with pipeline_test_db() as db:
        manifest = {
            "projectId": "proj_stage6_test",
            "version": 1,
            "scenes": [],
            "assembly": {
                "burnCaptions": False,
                "thumbnail": {
                    "prompt": "Dramatic movie poster",
                    "status": "idle",
                    "variants": [],
                },
                "status": "idle",
            },
        }
        project = Project(
            id="proj_stage6_test",
            user_id=DEFAULT_USER_ID,
            title="Assembly Test",
            format="cinematic_drama",
            version=1,
            status=ProjectStatus.DRAFT,
            manifest=manifest,
        )
        db.add(project)
        await db.commit()

        updated_project = await assemble_timeline_pipeline(
            project_id=project.id,
            db=db,
        )

        assembly = updated_project.manifest["assembly"]
        assert assembly["status"] == "completed"
        assert assembly["finalVideoUrl"] is not None
        assert assembly["thumbnail"]["selectedAssetUrl"] is not None
        assert updated_project.status == ProjectStatus.COMPLETED


@pytest.mark.asyncio
async def test_stage7_export_zip_bundle(pipeline_test_db) -> None:
    """Verify Stage 7: Project ZIP bundle packaging and transcoding presets."""
    async with pipeline_test_db() as db:
        manifest = {
            "projectId": "proj_stage7_test",
            "version": 1,
            "consistencies": {
                "characters": [],
                "objects": [],
            },
            "scenes": [],
            "assembly": {
                "finalVideoUrl": None,
                "bundleZipUrl": None,
            },
        }
        project = Project(
            id="proj_stage7_test",
            user_id=DEFAULT_USER_ID,
            title="Export Test",
            format="cinematic_drama",
            version=1,
            status=ProjectStatus.COMPLETED,
            manifest=manifest,
        )
        db.add(project)
        await db.commit()

        updated_project = await export_project_zip_bundle(
            project_id=project.id,
            db=db,
            include_presets=False,
        )

        assembly = updated_project.manifest["assembly"]
        assert assembly["bundleZipUrl"] is not None
        assert assembly["bundleZipUrl"].endswith(".zip")


@pytest.mark.asyncio
async def test_pipeline_http_endpoints(pipeline_test_db) -> None:
    """Verify all FastAPI Pipeline Router endpoints."""
    async def _override_db():
        async with pipeline_test_db() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db_session] = _override_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Create project
        create_resp = await client.post(
            "/api/v1/projects",
            json={
                "title": "API Test Project",
                "format": "cinematic_drama",
                "aspect_ratio": "16:9",
            },
        )
        assert create_resp.status_code == 201, create_resp.text
        proj_data = create_resp.json()
        project_id = proj_data["id"]

        # 2. Pitches
        p_resp = await client.post(
            f"/api/v1/projects/{project_id}/pipeline/pitches",
            json={"prompt": "A lone lighthouse keeper receives a mysterious transmission"},
        )
        assert p_resp.status_code == 200, p_resp.text
        pitches = p_resp.json()
        assert len(pitches) == 3

        # 3. Planner
        plan_resp = await client.post(
            f"/api/v1/projects/{project_id}/pipeline/planner",
            json={"pitch_index": 1, "user_prompt": "Lighthouse mystery transmission"},
        )
        assert plan_resp.status_code == 200, plan_resp.text
        manifest = plan_resp.json()["manifest"]
        assert len(manifest["scenes"]) >= 2

        # 4. Consistencies
        cons_resp = await client.post(
            f"/api/v1/projects/{project_id}/pipeline/consistencies",
            json={},
        )
        assert cons_resp.status_code == 200, cons_resp.text

        # 5. Keyframes
        kf_resp = await client.post(
            f"/api/v1/projects/{project_id}/pipeline/keyframes",
            json={},
        )
        assert kf_resp.status_code == 200, kf_resp.text

        # 6. Audio
        aud_resp = await client.post(
            f"/api/v1/projects/{project_id}/pipeline/audio",
            json={},
        )
        assert aud_resp.status_code == 200, aud_resp.text

        # 7. Video
        vid_resp = await client.post(
            f"/api/v1/projects/{project_id}/pipeline/video",
            json={},
        )
        assert vid_resp.status_code == 200, vid_resp.text

        # 8. Assembly
        asm_resp = await client.post(
            f"/api/v1/projects/{project_id}/pipeline/assembly",
            json={"burn_captions": False},
        )
        assert asm_resp.status_code == 200, asm_resp.text

        # 9. Export
        exp_resp = await client.post(
            f"/api/v1/projects/{project_id}/pipeline/export",
            json={"include_presets": False},
        )
        assert exp_resp.status_code == 200, exp_resp.text
        assert exp_resp.json()["status"] == "completed"
        assert exp_resp.json()["bundleZipUrl"].endswith(".zip")
