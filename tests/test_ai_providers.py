"""Tests for Visual, Video, TTS & Lip-Sync AI Providers (TASK-5.3, TASK-5.4, TASK-5.5, TASK-5.6)."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator, Dict, Optional

import pytest

from server.core.storage import StorageService
from server.providers.audio import MockTTSProvider
from server.providers.image import MockImageProvider, ReferenceImageInjectionHelper
from server.providers.lipsync import MockLipSyncProvider
from server.providers.video import MockVideoProvider


class InMemoryMinIOBucket:
    """Mock in-memory S3 bucket capturing uploads."""

    def __init__(self) -> None:
        self.objects: Dict[str, bytes] = {}

    async def upload_file(
        self,
        file_path: str,
        bucket: str,
        object_key: str,
        ExtraArgs: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.objects[f"{bucket}/{object_key}"] = Path(file_path).read_bytes()


@pytest.fixture
def mock_storage_service() -> StorageService:
    bucket = InMemoryMinIOBucket()

    @asynccontextmanager
    async def s3_factory() -> AsyncIterator[InMemoryMinIOBucket]:
        yield bucket

    return StorageService(s3_client_factory=s3_factory)


@pytest.mark.asyncio
async def test_image_provider_with_reference_injection(mock_storage_service: StorageService) -> None:
    """TASK-5.3 Verification: Generate image with reference conditioning; verify permanent S3 URL and variants."""
    provider = MockImageProvider(storage=mock_storage_service)

    conditioning = ReferenceImageInjectionHelper.inject_conditioning(
        prompt="Elena Vance standing on misty shoreline",
        reference_image_urls=["http://cdn.app/char_01_turnaround.png"],
        image_prompt_strength=0.7,
    )
    assert conditioning["image_url"] == "http://cdn.app/char_01_turnaround.png"
    assert conditioning["image_prompt_strength"] == 0.7

    result = await provider.generate_image(
        prompt=conditioning["prompt"],
        project_id="proj_img_test",
        subfolder="keyframes",
        num_variants=3,
    )
    assert result.public_url.startswith("http")
    assert "proj_img_test/keyframes" in result.storage_key
    assert len(result.variants) == 3


@pytest.mark.asyncio
async def test_video_provider_generation(mock_storage_service: StorageService) -> None:
    """TASK-5.4 Verification: Generate image-to-video; verify valid MP4 URL and duration."""
    provider = MockVideoProvider(storage=mock_storage_service)

    result = await provider.generate_video(
        prompt="Slow camera dolly push-in on Elena",
        project_id="proj_vid_test",
        scene_id="scene_01",
        start_image_url="http://cdn.app/keyframe_01.png",
        duration_sec=5.0,
    )
    assert result.video_url.startswith("http")
    assert result.duration_sec == 5.0
    assert "scenes/scene_01" in result.storage_key


@pytest.mark.asyncio
async def test_tts_provider_speech_and_word_timestamps(mock_storage_service: StorageService) -> None:
    """TASK-5.5 Verification: Synthesize speech; verify audio URL and word-level timing offsets."""
    provider = MockTTSProvider(storage=mock_storage_service)
    test_text = "The beacon was pulsing with unexpected frequencies."

    result = await provider.synthesize_speech(
        text=test_text,
        project_id="proj_audio_test",
        scene_id="scene_01",
        speaker_id="char_01",
    )
    assert result.audio_url.startswith("http")
    assert result.duration_sec > 0
    assert len(result.word_timestamps) == len(test_text.split())

    # Verify first and second word offsets
    assert result.word_timestamps[0]["word"] == "The"
    assert result.word_timestamps[0]["start"] == 0.0
    assert result.word_timestamps[0]["end"] > 0.0


@pytest.mark.asyncio
async def test_lipsync_provider_execution(mock_storage_service: StorageService) -> None:
    """TASK-5.6 Verification: Apply conditional lip sync to video and audio tracks."""
    provider = MockLipSyncProvider(storage=mock_storage_service)

    result = await provider.apply_lip_sync(
        video_url="http://cdn.app/scene_01_raw.mp4",
        audio_url="http://cdn.app/scene_01_dialogue.mp3",
        project_id="proj_sync_test",
        scene_id="scene_01",
    )
    assert result.video_url.startswith("http")
    assert result.duration_sec == 5.0
    assert "scenes/scene_01/lipsync" in result.storage_key
