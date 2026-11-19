"""Master JSON Manifest Specification in Pydantic v2 (TASK-1.4)."""

from __future__ import annotations

from typing import List, Literal, Optional, Set
from pydantic import BaseModel, ConfigDict, Field, model_validator

AssetStatus = Literal["idle", "queued", "generating", "completed", "failed"]
CharacterRole = Literal["protagonist", "antagonist", "supporting", "narrator"]
ObjectCategory = Literal["prop", "vehicle", "costume", "environment"]
DialogueVoiceProvider = Literal["elevenlabs", "google_tts", "azure"]
VoiceoverProvider = Literal["elevenlabs", "google_tts"]
SfxMode = Literal["stock", "generative", "none"]
AspectRatio = Literal["16:9", "9:16", "1:1"]
ResolutionPreset = Literal["1080p", "4k"]
VideoModel = Literal["kling_v3", "ltx_2_pro", "minimax_hailuo", "runway_gen3", "veo_2"]
ProjectFormat = Literal[
    "cinematic_drama",
    "documentary",
    "explainer",
    "podcast_clip",
    "vertical_short",
]
TransitionType = Literal["cut", "crossfade", "dip_to_black"]
SubtitleStyle = Literal[
    "subtitles_classic",
    "karaoke_active_word",
    "minimal_lower_third",
]


class StrictSchemaModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class CharacterConsistency(StrictSchemaModel):
    id: str = Field(..., min_length=1, description="Stable character ID, e.g. char_01")
    name: str = Field(..., min_length=1)
    role: CharacterRole
    description: str
    prompt360: str = Field(..., min_length=1)
    negativePrompt: Optional[str] = None
    status: AssetStatus = "idle"
    progressPercent: float = Field(default=0, ge=0, le=100)
    error: Optional[str] = None
    selectedAssetUrl: Optional[str] = None
    variants: List[str] = Field(default_factory=list)


class ObjectConsistency(StrictSchemaModel):
    id: str = Field(..., min_length=1, description="Stable object ID, e.g. obj_01")
    name: str = Field(..., min_length=1)
    category: ObjectCategory
    prompt360: str = Field(..., min_length=1)
    status: AssetStatus = "idle"
    progressPercent: float = Field(default=0, ge=0, le=100)
    error: Optional[str] = None
    selectedAssetUrl: Optional[str] = None
    variants: List[str] = Field(default_factory=list)


class DialogueLine(StrictSchemaModel):
    id: str = Field(..., min_length=1, description="e.g. dlg_01_01")
    speakerId: str = Field(..., min_length=1, description="References CharacterConsistency.id")
    voiceId: str = Field(..., min_length=1)
    voiceProvider: DialogueVoiceProvider = "elevenlabs"
    startOffsetSec: float = Field(..., ge=0)
    endOffsetSec: float = Field(..., gt=0)
    text: str = Field(..., min_length=1)
    assetUrl: Optional[str] = None
    status: AssetStatus = "idle"

    @model_validator(mode="after")
    def validate_offsets(self) -> "DialogueLine":
        if self.startOffsetSec >= self.endOffsetSec:
            raise ValueError(
                f"DialogueLine '{self.id}' startOffsetSec ({self.startOffsetSec}) "
                f"must be strictly less than endOffsetSec ({self.endOffsetSec})"
            )
        return self


class VoiceoverConfig(StrictSchemaModel):
    enabled: bool = True
    startOffsetSec: float = Field(default=0.0, ge=0)
    endOffsetSec: float = Field(default=5.0, gt=0)
    provider: VoiceoverProvider = "elevenlabs"
    voiceId: str = Field(..., min_length=1)
    text: str = ""
    assetUrl: Optional[str] = None
    status: AssetStatus = "idle"

    @model_validator(mode="after")
    def validate_vo_offsets(self) -> "VoiceoverConfig":
        if self.enabled and self.startOffsetSec >= self.endOffsetSec:
            raise ValueError(
                f"Voiceover startOffsetSec ({self.startOffsetSec}) "
                f"must be strictly less than endOffsetSec ({self.endOffsetSec})"
            )
        return self


class SfxConfig(StrictSchemaModel):
    mode: SfxMode = "none"
    prompt: str = ""
    assetUrl: Optional[str] = None
    status: AssetStatus = "idle"


class SceneAudio(StrictSchemaModel):
    voiceover: VoiceoverConfig
    dialogue: List[DialogueLine] = Field(default_factory=list)
    sfx: SfxConfig
    mergedSceneAudioUrl: Optional[str] = None
    status: AssetStatus = "idle"


class SceneKeyframe(StrictSchemaModel):
    refIds: List[str] = Field(default_factory=list)
    prompt: str = Field(..., min_length=1)
    negativePrompt: Optional[str] = None
    aspectRatio: AspectRatio = "16:9"
    status: AssetStatus = "idle"
    progressPercent: float = Field(default=0, ge=0, le=100)
    selectedAssetUrl: Optional[str] = None
    variants: List[str] = Field(default_factory=list)


class SceneVideo(StrictSchemaModel):
    model: VideoModel = "kling_v3"
    supportsNativeAudio: bool = False
    requiresLipSync: bool = False
    motionPrompt: str = Field(..., min_length=1)
    cameraMotion: Optional[str] = None
    rawVideoUrl: Optional[str] = None
    lipSyncedVideoUrl: Optional[str] = None
    status: AssetStatus = "idle"
    progressPercent: float = Field(default=0, ge=0, le=100)
    error: Optional[str] = None


class SceneTimestamp(StrictSchemaModel):
    startSec: float = Field(..., ge=0)
    endSec: float = Field(..., gt=0)

    @model_validator(mode="after")
    def validate_timestamp_range(self) -> "SceneTimestamp":
        if self.startSec >= self.endSec:
            raise ValueError(
                f"Scene timestamp startSec ({self.startSec}) must be strictly less than endSec ({self.endSec})"
            )
        return self


class CameraSpec(StrictSchemaModel):
    angle: str = Field(..., min_length=1)
    movement: str = Field(..., min_length=1)
    lens: str = Field(..., min_length=1)


class SceneNode(StrictSchemaModel):
    sceneNumber: int = Field(..., ge=1)
    id: str = Field(..., min_length=1)
    timestamp: SceneTimestamp
    visualDescription: str = Field(..., min_length=1)
    camera: CameraSpec
    keyframe: SceneKeyframe
    audio: SceneAudio
    video: SceneVideo


class GlobalStyle(StrictSchemaModel):
    aspectRatio: AspectRatio = "16:9"
    resolution: ResolutionPreset = "1080p"
    visualStylePrompt: str = Field(..., min_length=1)
    colorGradingPreset: str = Field(..., min_length=1)
    musicGenrePrompt: Optional[str] = None


class ConsistenciesContainer(StrictSchemaModel):
    characters: List[CharacterConsistency] = Field(default_factory=list)
    objects: List[ObjectConsistency] = Field(default_factory=list)


class OutroEndFrame(StrictSchemaModel):
    prompt: str = Field(..., min_length=1)
    selectedAssetUrl: Optional[str] = None
    variants: List[str] = Field(default_factory=list)
    status: AssetStatus = "idle"


class ThumbnailSpec(StrictSchemaModel):
    prompt: str = Field(..., min_length=1)
    selectedAssetUrl: Optional[str] = None
    variants: List[str] = Field(default_factory=list)
    status: AssetStatus = "idle"


class AssemblyConfig(StrictSchemaModel):
    transitionType: TransitionType = "cut"
    transitionDurationSec: float = Field(default=0.5, ge=0, le=5.0)
    backgroundMusicUrl: Optional[str] = None
    burnCaptions: bool = True
    subtitleStyle: SubtitleStyle = "subtitles_classic"
    thumbnail: ThumbnailSpec
    finalVideoUrl: Optional[str] = None
    bundleZipUrl: Optional[str] = None
    status: AssetStatus = "idle"
    progressPercent: float = Field(default=0, ge=0, le=100)


class MasterManifest(StrictSchemaModel):
    projectId: str = Field(..., min_length=1)
    version: int = Field(default=1, ge=1)
    title: str = Field(..., min_length=1)
    format: ProjectFormat = "cinematic_drama"
    contextArtifactIds: List[str] = Field(default_factory=list)
    globalStyle: GlobalStyle
    consistencies: ConsistenciesContainer
    scenes: List[SceneNode] = Field(default_factory=list)
    outroEndFrame: OutroEndFrame
    assembly: AssemblyConfig

    @model_validator(mode="after")
    def validate_cross_references(self) -> "MasterManifest":
        character_ids: Set[str] = {c.id for c in self.consistencies.characters}
        object_ids: Set[str] = {o.id for o in self.consistencies.objects}
        valid_ref_ids: Set[str] = character_ids | object_ids

        for scene in self.scenes:
            for ref_id in scene.keyframe.refIds:
                if ref_id not in valid_ref_ids:
                    raise ValueError(
                        f"Scene '{scene.id}' keyframe references unknown refId '{ref_id}'. "
                        f"Available consistency IDs: {sorted(valid_ref_ids)}"
                    )
            for dlg in scene.audio.dialogue:
                if dlg.speakerId not in character_ids:
                    raise ValueError(
                        f"Scene '{scene.id}' dialogue '{dlg.id}' references unknown speakerId "
                        f"'{dlg.speakerId}'. Available character IDs: {sorted(character_ids)}"
                    )
        return self
