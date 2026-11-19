"""LLM Engine with Gemini & Claude Structured Output Enforcement (TASK-5.2)."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, Optional

from server.core.config import Settings, get_settings
from server.prompts.story_prompts import (
    PLANNER_SYSTEM_INSTRUCTION,
    build_character_turnaround_prompt,
    build_object_turnaround_prompt,
    build_planner_user_prompt,
)
from server.providers.base import LLMProvider
from server.schemas.manifest import MasterManifest

logger = logging.getLogger(__name__)


class GeminiLLMProvider(LLMProvider):
    """Google Gemini 1.5/2.0 Pro adapter enforcing MasterManifest JSON schema."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()

    async def generate_structured_manifest(
        self,
        user_prompt: str,
        format_type: str = "cinematic_drama",
        aspect_ratio: str = "16:9",
        context_markdown: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Call Gemini Pro with MasterManifest structured output enforcement."""
        api_key = self.settings.GEMINI_API_KEY
        if not api_key:
            logger.info("GEMINI_API_KEY not configured; using deterministic mock provider.")
            return await MockLLMProvider().generate_structured_manifest(
                user_prompt, format_type, aspect_ratio, context_markdown
            )

        prompt_text = build_planner_user_prompt(
            user_prompt=user_prompt,
            format_type=format_type,
            aspect_ratio=aspect_ratio,
            context_markdown=context_markdown,
        )

        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model="gemini-2.5-pro",
                contents=[prompt_text],
                config=types.GenerateContentConfig(
                    system_instruction=PLANNER_SYSTEM_INSTRUCTION,
                    response_mime_type="application/json",
                    response_schema=MasterManifest,
                    temperature=0.3,
                ),
            )

            if response.text:
                data = json.loads(response.text)
                # Validate against Pydantic schema
                validated = MasterManifest.model_validate(data)
                return validated.model_dump(by_alias=True)

        except Exception as exc:
            logger.warning("Gemini 2.5 SDK call failed (%s); attempting fallback generation.", exc)

        # Fallback to Mock if API is inaccessible or fails
        return await MockLLMProvider().generate_structured_manifest(
            user_prompt, format_type, aspect_ratio, context_markdown
        )


class ClaudeLLMProvider(LLMProvider):
    """Anthropic Claude 3.5 Sonnet adapter with tool-calling schema enforcement."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()

    async def generate_structured_manifest(
        self,
        user_prompt: str,
        format_type: str = "cinematic_drama",
        aspect_ratio: str = "16:9",
        context_markdown: Optional[str] = None,
    ) -> Dict[str, Any]:
        api_key = self.settings.ANTHROPIC_API_KEY
        if not api_key:
            logger.info("ANTHROPIC_API_KEY not configured; using mock provider.")
            return await MockLLMProvider().generate_structured_manifest(
                user_prompt, format_type, aspect_ratio, context_markdown
            )

        try:
            import anthropic
            client = anthropic.AsyncAnthropic(api_key=api_key)
            prompt_text = build_planner_user_prompt(
                user_prompt=user_prompt,
                format_type=format_type,
                aspect_ratio=aspect_ratio,
                context_markdown=context_markdown,
            )

            # Claude tool calling for schema enforcement
            tool_schema = MasterManifest.model_json_schema()
            response = await client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=4096,
                system=PLANNER_SYSTEM_INSTRUCTION,
                messages=[{"role": "user", "content": prompt_text}],
                tools=[
                    {
                        "name": "generate_master_manifest",
                        "description": "Output the complete Master JSON video production manifest",
                        "input_schema": tool_schema,
                    }
                ],
                tool_choice={"type": "tool", "name": "generate_master_manifest"},
            )

            for block in response.content:
                if block.type == "tool_use" and block.name == "generate_master_manifest":
                    manifest_data = block.input
                    validated = MasterManifest.model_validate(manifest_data)
                    return validated.model_dump(by_alias=True)

        except Exception as exc:
            logger.warning("Claude tool-use call failed (%s); falling back to mock provider.", exc)

        return await MockLLMProvider().generate_structured_manifest(
            user_prompt, format_type, aspect_ratio, context_markdown
        )


class MockLLMProvider(LLMProvider):
    """Deterministic High-Fidelity Master Manifest Generator for testing and offline modes."""

    async def generate_structured_manifest(
        self,
        user_prompt: str,
        format_type: str = "cinematic_drama",
        aspect_ratio: str = "16:9",
        context_markdown: Optional[str] = None,
    ) -> Dict[str, Any]:
        clean_title = user_prompt[:30].strip() or "The Horizon Signal"
        style_prompt = "35mm anamorphic film, moody coastal lighting, Kodak 2383 stock"

        char_prompt = build_character_turnaround_prompt(
            character_name="Elena Vance",
            role="protagonist",
            visual_description="Signals analyst in her late 20s, weathered linen jacket, wind-blown dark hair",
            wardrobe="weathered linen field coat, dark rugged trousers",
            style_preset=style_prompt,
        )

        obj_prompt = build_object_turnaround_prompt(
            object_name="Telemetry Beacon",
            category="prop",
            visual_description="Weathered titanium cylinder with pulsing amber LED arrays and rotary dials",
            style_preset=style_prompt,
        )

        manifest = {
            "projectId": "proj_generated",
            "version": 1,
            "title": clean_title,
            "format": format_type,
            "contextArtifactIds": [],
            "globalStyle": {
                "aspectRatio": aspect_ratio,
                "resolution": "1080p",
                "visualStylePrompt": style_prompt,
                "colorGradingPreset": "kodak_2383_teal_orange",
                "musicGenrePrompt": "ambient analog synth with deep ocean sub-bass",
            },
            "consistencies": {
                "characters": [
                    {
                        "id": "char_01",
                        "name": "Elena Vance",
                        "role": "protagonist",
                        "description": "Marine signals analyst investigating unmapped coastal telemetry",
                        "prompt360": char_prompt,
                        "status": "idle",
                        "progressPercent": 0,
                        "selectedAssetUrl": None,
                        "variants": [],
                    }
                ],
                "objects": [
                    {
                        "id": "obj_01",
                        "name": "Telemetry Beacon",
                        "category": "prop",
                        "prompt360": obj_prompt,
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
                    "timestamp": {"startSec": 0.0, "endSec": 5.0},
                    "visualDescription": "Elena stands at the Pacific tide line as a mechanical drone glides silently overhead.",
                    "camera": {
                        "angle": "Low-angle medium wide",
                        "movement": "Slow dolly push-in",
                        "lens": "35mm shallow depth of field, f/1.8",
                    },
                    "keyframe": {
                        "refIds": ["char_01", "obj_01"],
                        "prompt": "Elena Vance [char_01] stands near the cold shoreline holding the telemetry beacon [obj_01], mist in the distance. 35mm film.",
                        "status": "idle",
                        "progressPercent": 0,
                        "selectedAssetUrl": None,
                        "variants": [],
                    },
                    "audio": {
                        "voiceover": {
                            "enabled": True,
                            "startOffsetSec": 0.0,
                            "endOffsetSec": 3.5,
                            "provider": "elevenlabs",
                            "voiceId": "narrator_deep_01",
                            "text": "The signal had been broadcasting since before the storm began.",
                            "assetUrl": None,
                            "status": "idle",
                        },
                        "dialogue": [],
                        "sfx": {
                            "mode": "generative",
                            "prompt": "Ocean waves crashing with distant mechanical drone hum",
                            "assetUrl": None,
                            "status": "idle",
                        },
                        "mergedSceneAudioUrl": None,
                        "status": "idle",
                    },
                    "video": {
                        "model": "kling_v3",
                        "supportsNativeAudio": False,
                        "requiresLipSync": False,
                        "motionPrompt": "Slow camera dolly forward as wind ruffles her coat and sea spray glistens",
                        "rawVideoUrl": None,
                        "lipSyncedVideoUrl": None,
                        "status": "idle",
                        "progressPercent": 0,
                    },
                },
                {
                    "sceneNumber": 2,
                    "id": "scene_02",
                    "timestamp": {"startSec": 5.0, "endSec": 10.0},
                    "visualDescription": "Close-up on the telemetry beacon displaying a rhythmic amber sequence.",
                    "camera": {
                        "angle": "Intimate macro close-up",
                        "movement": "Subtle handheld breathing motion",
                        "lens": "85mm macro lens, tack-sharp focus on indicators",
                    },
                    "keyframe": {
                        "refIds": ["obj_01"],
                        "prompt": "Close-up of the telemetry beacon [obj_01] with glowing amber dials in Elena's hands. Soft ocean background bokeh.",
                        "status": "idle",
                        "progressPercent": 0,
                        "selectedAssetUrl": None,
                        "variants": [],
                    },
                    "audio": {
                        "voiceover": {
                            "enabled": False,
                            "startOffsetSec": 0.0,
                            "endOffsetSec": 1.0,
                            "provider": "elevenlabs",
                            "voiceId": "narrator_deep_01",
                            "text": "",
                            "assetUrl": None,
                            "status": "idle",
                        },
                        "dialogue": [
                            {
                                "id": "dlg_01",
                                "speakerId": "char_01",
                                "voiceId": "elena_voice_02",
                                "voiceProvider": "elevenlabs",
                                "startOffsetSec": 0.5,
                                "endOffsetSec": 4.5,
                                "text": "It's answering. The coordinates match the offshore reef.",
                                "assetUrl": None,
                                "status": "idle",
                            }
                        ],
                        "sfx": {
                            "mode": "generative",
                            "prompt": "High frequency rotary clicks and warm electronic hum",
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
                        "motionPrompt": "Subtle rack focus from dials to Elena's focused expression",
                        "rawVideoUrl": None,
                        "lipSyncedVideoUrl": None,
                        "status": "idle",
                        "progressPercent": 0,
                    },
                },
            ],
            "outroEndFrame": {
                "prompt": "Wide aerial pullback of the empty coastline under twilight skies, glowing telemetry beacon on the shoreline",
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
                    "prompt": "Elena Vance standing on the misty beach with glowing beacon, cinematic poster composition",
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

        # Validate with Pydantic
        validated = MasterManifest.model_validate(manifest)
        return validated.model_dump(by_alias=True)


def get_llm_provider(name: Optional[str] = None) -> LLMProvider:
    """Factory selecting configured LLM provider."""
    settings = get_settings()
    selected = (name or settings.LLM_PROVIDER or "gemini").lower()
    if selected == "claude" and settings.ANTHROPIC_API_KEY:
        return ClaudeLLMProvider(settings)
    if selected == "gemini" and settings.GEMINI_API_KEY:
        return GeminiLLMProvider(settings)
    return MockLLMProvider()
