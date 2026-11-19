"""Tests for LLM Engine, Prompt Architecture & MasterManifest Output Enforcement (TASK-5.2)."""

from __future__ import annotations

import pytest

from server.prompts.story_prompts import (
    build_character_turnaround_prompt,
    build_keyframe_prompt,
    build_object_turnaround_prompt,
    build_planner_user_prompt,
)
from server.providers.llm import MockLLMProvider
from server.schemas.manifest import MasterManifest


def test_character_360_turnaround_prompt_rules() -> None:
    prompt = build_character_turnaround_prompt(
        character_name="Elena Vance",
        role="protagonist",
        visual_description="Signals analyst with dark hair",
        wardrobe="Linen field coat",
        style_preset="35mm anamorphic film",
    )
    assert "Elena Vance" in prompt
    assert "front-facing view" in prompt
    assert "side profile view" in prompt
    assert "three-quarter dynamic angle" in prompt
    assert "rear back view" in prompt
    assert "neutral solid studio grey background" in prompt.lower()


def test_object_turnaround_prompt_rules() -> None:
    prompt = build_object_turnaround_prompt(
        object_name="Telemetry Beacon",
        category="prop",
        visual_description="Titanium housing with amber LEDs",
    )
    assert "Telemetry Beacon" in prompt
    assert "Multi-angle product showcase" in prompt
    assert "Clean neutral gradient studio background" in prompt


def test_keyframe_prompt_reference_injection() -> None:
    prompt = build_keyframe_prompt(
        scene_description="Elena inspects the shore",
        character_refs=[{"id": "char_01", "name": "Elena Vance"}],
        object_refs=[{"id": "obj_01", "name": "Telemetry Beacon"}],
        camera_directive="Low-angle slow dolly push-in",
        global_style="35mm moody film",
    )
    assert "Elena Vance [char_01]" in prompt
    assert "Telemetry Beacon [obj_01]" in prompt
    assert "Low-angle slow dolly push-in" in prompt


@pytest.mark.asyncio
async def test_llm_structured_manifest_generation_and_pydantic_validation() -> None:
    """TASK-5.2 Verification: Generate script; assert output strictly parses into MasterManifest without schema violations."""
    provider = MockLLMProvider()
    manifest_data = await provider.generate_structured_manifest(
        user_prompt="Elena discovers a mysterious telemetry signal transmitting from the misty coastline",
        format_type="cinematic_drama",
        aspect_ratio="16:9",
    )

    # Validate against strict Pydantic MasterManifest model
    manifest = MasterManifest.model_validate(manifest_data)
    assert manifest.format == "cinematic_drama"
    assert manifest.globalStyle.aspectRatio == "16:9"
    assert len(manifest.consistencies.characters) >= 1
    assert manifest.consistencies.characters[0].prompt360 is not None
    assert len(manifest.scenes) >= 2

    # Verify scene chronological chaining
    for i in range(1, len(manifest.scenes)):
        assert manifest.scenes[i].timestamp.startSec == manifest.scenes[i - 1].timestamp.endSec

    # Verify keyframe and audio integrity
    for scene in manifest.scenes:
        assert scene.camera.movement is not None
        assert scene.keyframe.prompt is not None
        assert scene.video.model is not None
        duration = scene.timestamp.endSec - scene.timestamp.startSec
        if scene.audio.voiceover and scene.audio.voiceover.enabled:
            assert scene.audio.voiceover.endOffsetSec <= duration
