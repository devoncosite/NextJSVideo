"""Tests for SQLAlchemy 2.0 Async Session, Relational Entities, JSONB Manifest, and Schemas (TASK-1.1, TASK-1.2, TASK-1.4)."""

from __future__ import annotations

import asyncio
from typing import Any, Dict

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from server.core.config import Settings
from server.core.database import build_engine_kwargs, check_database_health
from server.models import (
    Base,
    ContextArtifact,
    ContextSourceType,
    JobQueueRecord,
    JobStage,
    JobStatus,
    Project,
    ProjectStatus,
    User,
)
from server.schemas.manifest import MasterManifest


def sample_valid_manifest(project_id: str = "proj_98a7f") -> Dict[str, Any]:
    return {
        "projectId": project_id,
        "version": 1,
        "title": "The Horizon Signal",
        "format": "cinematic_drama",
        "contextArtifactIds": ["ctx_pdf_01"],
        "globalStyle": {
            "aspectRatio": "16:9",
            "resolution": "1080p",
            "visualStylePrompt": "35mm anamorphic film, moody coastal lighting",
            "colorGradingPreset": "kodak_2383_teal_orange",
            "musicGenrePrompt": "ambient analog synth",
        },
        "consistencies": {
            "characters": [
                {
                    "id": "char_01",
                    "name": "Elena Vance",
                    "role": "protagonist",
                    "description": "Marine signals analyst in her late 20s",
                    "prompt360": "Woman in her late 20s, weathered linen coat, 360-degree character turnaround sheet",
                    "status": "completed",
                    "progressPercent": 100,
                    "selectedAssetUrl": "http://127.0.0.1:9000/studio-assets/proj_98a7f/chars/char_01.png",
                    "variants": ["http://127.0.0.1:9000/studio-assets/proj_98a7f/chars/char_01.png"],
                }
            ],
            "objects": [
                {
                    "id": "obj_01",
                    "name": "Telemetry Beacon",
                    "category": "prop",
                    "prompt360": "Brushed titanium marine telemetry beacon, 360-degree turnaround sheet",
                    "status": "idle",
                    "progressPercent": 0,
                    "selectedAssetUrl": None,
                    "variants": [],
                }
            ],
        },
        "scenes": [
            {
                "sceneNumber": 1,
                "id": "scene_01",
                "timestamp": {"startSec": 0, "endSec": 10},
                "visualDescription": "Elena stands at the shoreline holding the telemetry beacon.",
                "camera": {
                    "angle": "Low-angle medium wide",
                    "movement": "Slow dolly push-in",
                    "lens": "35mm anamorphic",
                },
                "keyframe": {
                    "refIds": ["char_01", "obj_01"],
                    "prompt": "Elena [char_01] holding [obj_01] at the rocky shoreline.",
                    "aspectRatio": "16:9",
                    "status": "idle",
                    "progressPercent": 0,
                    "selectedAssetUrl": None,
                    "variants": [],
                },
                "audio": {
                    "voiceover": {
                        "enabled": True,
                        "startOffsetSec": 0.0,
                        "endOffsetSec": 4.0,
                        "provider": "elevenlabs",
                        "voiceId": "narrator_deep_01",
                        "text": "She never expected the signal to reach the coast.",
                        "assetUrl": None,
                        "status": "idle",
                    },
                    "dialogue": [
                        {
                            "id": "dlg_01_01",
                            "speakerId": "char_01",
                            "voiceId": "elena_voice_02",
                            "voiceProvider": "elevenlabs",
                            "startOffsetSec": 4.0,
                            "endOffsetSec": 9.5,
                            "text": "Wait—is that ours? It's coming straight toward us!",
                            "assetUrl": None,
                            "status": "idle",
                        }
                    ],
                    "sfx": {
                        "mode": "generative",
                        "prompt": "Crashing ocean waves with low frequency pulse",
                        "assetUrl": None,
                        "status": "idle",
                    },
                    "mergedSceneAudioUrl": None,
                    "status": "idle",
                },
                "video": {
                    "model": "kling_v3",
                    "supportsNativeAudio": False,
                    "requiresLipSync": True,
                    "motionPrompt": "Slow push-in as wind blows her hair",
                    "rawVideoUrl": None,
                    "lipSyncedVideoUrl": None,
                    "status": "idle",
                    "progressPercent": 0,
                },
            }
        ],
        "outroEndFrame": {
            "prompt": "Wide aerial pullback of the shoreline at dusk",
            "selectedAssetUrl": None,
            "variants": [],
            "status": "idle",
        },
        "assembly": {
            "transitionType": "cut",
            "transitionDurationSec": 0.5,
            "backgroundMusicUrl": None,
            "burnCaptions": True,
            "subtitleStyle": "karaoke_active_word",
            "thumbnail": {
                "prompt": "Dramatic close-up of Elena with glowing beacon",
                "selectedAssetUrl": None,
                "variants": [],
                "status": "idle",
            },
            "finalVideoUrl": None,
            "bundleZipUrl": None,
            "status": "idle",
            "progressPercent": 0,
        },
    }


def test_engine_pool_parameters_configured_for_postgres() -> None:
    """TASK-1.1: Verify pool_size=20, max_overflow=10, pool_recycle=1800, pool_pre_ping=True."""
    settings = Settings()
    kwargs = build_engine_kwargs(settings.DATABASE_URL, settings)
    assert kwargs["pool_size"] == 20
    assert kwargs["max_overflow"] == 10
    assert kwargs["pool_recycle"] == 1800
    assert kwargs["pool_pre_ping"] is True


@pytest.mark.asyncio
async def test_concurrent_session_checkout_and_select_1() -> None:
    """TASK-1.1: Verify concurrent async session checkouts executing SELECT 1."""
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    results = await asyncio.gather(*(check_database_health(test_engine) for _ in range(5)))
    assert all(results)
    await test_engine.dispose()


@pytest.mark.asyncio
async def test_relational_models_crud_and_cascade_delete() -> None:
    """TASK-1.2: Verify User, Project (JSONB manifest), ContextArtifact, and JobQueueRecord constraints and cascades."""
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        # Enable SQLite foreign keys for cascade testing
        await session.execute(select(1))
        user = User(
            email="director@cineforge.ai",
            hashed_password="$2b$12$hashedpasswordvalue",
            name="Aria Chen",
        )
        session.add(user)
        await session.flush()

        manifest_dict = sample_valid_manifest("proj_test01")
        project = Project(
            id="proj_test01",
            user_id=user.id,
            title=manifest_dict["title"],
            format=manifest_dict["format"],
            version=1,
            manifest=manifest_dict,
            status=ProjectStatus.DRAFT,
        )
        session.add(project)
        await session.flush()

        artifact = ContextArtifact(
            id="ctx_pdf_01",
            project_id=project.id,
            content_hash="a" * 64,
            source_type=ContextSourceType.PDF,
            original_filename="production_bible.pdf",
            storage_path="/proj_test01/raw_context/aaaa.pdf",
            extracted_markdown="# Production Bible\nScene notes.",
            summary_json={"core_narrative": "Coastal signal discovery"},
        )
        job = JobQueueRecord(
            project_id=project.id,
            stage=JobStage.CONSISTENCIES,
            target_id="char_01",
            arq_job_id="arq_job_991",
            status=JobStatus.COMPLETED,
            retry_count=0,
        )
        session.add_all([artifact, job])
        await session.commit()

    async with session_factory() as session:
        fetched = await session.get(Project, "proj_test01")
        assert fetched is not None
        assert fetched.manifest["projectId"] == "proj_test01"
        assert fetched.manifest["consistencies"]["characters"][0]["name"] == "Elena Vance"

        await session.delete(fetched)
        await session.commit()

    async with session_factory() as session:
        remaining_artifacts = (await session.execute(select(ContextArtifact))).scalars().all()
        remaining_jobs = (await session.execute(select(JobQueueRecord))).scalars().all()
        assert len(remaining_artifacts) == 0
        assert len(remaining_jobs) == 0

    await test_engine.dispose()


def test_pydantic_manifest_validation_and_cross_reference_guards() -> None:
    """TASK-1.4: Verify Pydantic MasterManifest enforces timestamp order and refIds integrity."""
    raw = sample_valid_manifest()
    validated = MasterManifest.model_validate(raw)
    assert validated.projectId == "proj_98a7f"

    # Invalid timestamp range (startSec >= endSec)
    bad_ts = sample_valid_manifest()
    bad_ts["scenes"][0]["timestamp"] = {"startSec": 12, "endSec": 8}
    with pytest.raises(ValidationError) as ts_err:
        MasterManifest.model_validate(bad_ts)
    assert "startSec" in str(ts_err.value)

    # Dangling refId not in consistencies
    bad_ref = sample_valid_manifest()
    bad_ref["scenes"][0]["keyframe"]["refIds"] = ["char_01", "obj_999_missing"]
    with pytest.raises(ValidationError) as ref_err:
        MasterManifest.model_validate(bad_ref)
    assert "obj_999_missing" in str(ref_err.value)

    # Dangling dialogue speakerId
    bad_speaker = sample_valid_manifest()
    bad_speaker["scenes"][0]["audio"]["dialogue"][0]["speakerId"] = "char_unknown"
    with pytest.raises(ValidationError) as spk_err:
        MasterManifest.model_validate(bad_speaker)
    assert "char_unknown" in str(spk_err.value)
