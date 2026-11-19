"""Abstract Base Classes & Interfaces for External AI Providers (TASK-5.1)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ImageResult:
    """Standardized output of visual image generation."""

    public_url: str
    storage_key: str
    variants: List[str] = field(default_factory=list)
    provider: str = "flux"
    seed: Optional[int] = None


@dataclass
class VideoResult:
    """Standardized output of video generation."""

    video_url: str
    storage_key: str
    duration_sec: float
    supports_native_audio: bool = False
    provider: str = "kling"


@dataclass
class AudioResult:
    """Standardized output of speech and sound synthesis."""

    audio_url: str
    storage_key: str
    duration_sec: float
    word_timestamps: List[Dict[str, Any]] = field(default_factory=list)
    provider: str = "elevenlabs"


@dataclass
class LipSyncResult:
    """Standardized output of conditional lip-sync engine."""

    video_url: str
    storage_key: str
    duration_sec: float
    provider: str = "synclabs"


class LLMProvider(ABC):
    """Abstract interface for planning and script generation language models."""

    @abstractmethod
    async def generate_structured_manifest(
        self,
        user_prompt: str,
        format_type: str = "cinematic_drama",
        aspect_ratio: str = "16:9",
        context_markdown: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate complete Master JSON manifest conforming strictly to schema."""
        pass


class ImageGenProvider(ABC):
    """Abstract interface for character turnaround, object, and keyframe generation."""

    @abstractmethod
    async def generate_image(
        self,
        prompt: str,
        project_id: str,
        subfolder: str = "keyframes",
        aspect_ratio: str = "16:9",
        negative_prompt: Optional[str] = None,
        reference_image_urls: Optional[List[str]] = None,
        image_prompt_strength: float = 0.65,
        num_variants: int = 1,
    ) -> ImageResult:
        """Generate image, download from CDN, upload to permanent S3/R2 storage, and return ImageResult."""
        pass


class VideoGenProvider(ABC):
    """Abstract interface for scene video generation."""

    @abstractmethod
    async def generate_video(
        self,
        prompt: str,
        project_id: str,
        scene_id: str,
        start_image_url: str,
        end_image_url: Optional[str] = None,
        duration_sec: float = 5.0,
        aspect_ratio: str = "16:9",
    ) -> VideoResult:
        """Generate video from keyframes, persist to permanent S3/R2 storage, and return VideoResult."""
        pass


class TTSProvider(ABC):
    """Abstract interface for voiceover and dialogue synthesis."""

    @abstractmethod
    async def synthesize_speech(
        self,
        text: str,
        project_id: str,
        scene_id: str,
        speaker_id: str,
        voice_id: Optional[str] = None,
    ) -> AudioResult:
        """Synthesize spoken audio, extract word timestamps, persist MP3 to S3, and return AudioResult."""
        pass


class LipSyncProvider(ABC):
    """Abstract interface for conditional lip synchronization."""

    @abstractmethod
    async def apply_lip_sync(
        self,
        video_url: str,
        audio_url: str,
        project_id: str,
        scene_id: str,
    ) -> LipSyncResult:
        """Apply lip synchronization to video clip with audio, persist result, and return LipSyncResult."""
        pass
