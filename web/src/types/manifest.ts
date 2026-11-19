import { z } from "zod";

/**
 * Master JSON Manifest Specification (TASK-1.4)
 * Synchronized with server/schemas/manifest.py (Pydantic v2) and shared/schemas/master_manifest.schema.json
 */

export const AssetStatusSchema = z.enum(["idle", "queued", "generating", "completed", "failed"]);
export type AssetStatus = z.infer<typeof AssetStatusSchema>;

export const CharacterConsistencySchema = z.object({
  id: z.string().min(1),
  name: z.string().min(1),
  role: z.enum(["protagonist", "antagonist", "supporting", "narrator"]),
  description: z.string(),
  prompt360: z.string().min(1),
  negativePrompt: z.string().optional(),
  status: AssetStatusSchema,
  progressPercent: z.number().min(0).max(100),
  error: z.string().nullable().optional(),
  selectedAssetUrl: z.string().nullable(),
  variants: z.array(z.string()),
});
export type CharacterConsistency = z.infer<typeof CharacterConsistencySchema>;

export const ObjectConsistencySchema = z.object({
  id: z.string().min(1),
  name: z.string().min(1),
  category: z.enum(["prop", "vehicle", "costume", "environment"]),
  prompt360: z.string().min(1),
  status: AssetStatusSchema,
  progressPercent: z.number().min(0).max(100),
  error: z.string().nullable().optional(),
  selectedAssetUrl: z.string().nullable(),
  variants: z.array(z.string()),
});
export type ObjectConsistency = z.infer<typeof ObjectConsistencySchema>;

export const DialogueLineSchema = z
  .object({
    id: z.string().min(1),
    speakerId: z.string().min(1),
    voiceId: z.string().min(1),
    voiceProvider: z.enum(["elevenlabs", "google_tts", "azure"]),
    startOffsetSec: z.number().min(0),
    endOffsetSec: z.number().gt(0),
    text: z.string().min(1),
    assetUrl: z.string().nullable(),
    status: AssetStatusSchema,
  })
  .refine((data) => data.startOffsetSec < data.endOffsetSec, {
    message: "DialogueLine startOffsetSec must be strictly less than endOffsetSec",
    path: ["endOffsetSec"],
  });
export type DialogueLine = z.infer<typeof DialogueLineSchema>;

export const SceneAudioSchema = z.object({
  voiceover: z
    .object({
      enabled: z.boolean(),
      startOffsetSec: z.number().min(0),
      endOffsetSec: z.number().gt(0),
      provider: z.enum(["elevenlabs", "google_tts"]),
      voiceId: z.string().min(1),
      text: z.string(),
      assetUrl: z.string().nullable(),
      status: AssetStatusSchema,
    })
    .refine((vo) => !vo.enabled || vo.startOffsetSec < vo.endOffsetSec, {
      message: "Voiceover startOffsetSec must be strictly less than endOffsetSec",
      path: ["endOffsetSec"],
    }),
  dialogue: z.array(DialogueLineSchema),
  sfx: z.object({
    mode: z.enum(["stock", "generative", "none"]),
    prompt: z.string(),
    assetUrl: z.string().nullable(),
    status: AssetStatusSchema,
  }),
  mergedSceneAudioUrl: z.string().nullable(),
  status: AssetStatusSchema,
});
export type SceneAudio = z.infer<typeof SceneAudioSchema>;

export const SceneKeyframeSchema = z.object({
  refIds: z.array(z.string()),
  prompt: z.string().min(1),
  negativePrompt: z.string().optional(),
  aspectRatio: z.enum(["16:9", "9:16", "1:1"]),
  status: AssetStatusSchema,
  progressPercent: z.number().min(0).max(100),
  selectedAssetUrl: z.string().nullable(),
  variants: z.array(z.string()),
});
export type SceneKeyframe = z.infer<typeof SceneKeyframeSchema>;

export const SceneVideoSchema = z.object({
  model: z.enum(["kling_v3", "ltx_2_pro", "minimax_hailuo", "runway_gen3", "veo_2"]),
  supportsNativeAudio: z.boolean(),
  requiresLipSync: z.boolean(),
  motionPrompt: z.string().min(1),
  cameraMotion: z.string().optional(),
  rawVideoUrl: z.string().nullable(),
  lipSyncedVideoUrl: z.string().nullable(),
  status: AssetStatusSchema,
  progressPercent: z.number().min(0).max(100),
  error: z.string().nullable().optional(),
});
export type SceneVideo = z.infer<typeof SceneVideoSchema>;

export const SceneNodeSchema = z.object({
  sceneNumber: z.number().int().min(1),
  id: z.string().min(1),
  timestamp: z
    .object({
      startSec: z.number().min(0),
      endSec: z.number().gt(0),
    })
    .refine((ts) => ts.startSec < ts.endSec, {
      message: "Scene timestamp startSec must be strictly less than endSec",
      path: ["endSec"],
    }),
  visualDescription: z.string().min(1),
  camera: z.object({
    angle: z.string().min(1),
    movement: z.string().min(1),
    lens: z.string().min(1),
  }),
  keyframe: SceneKeyframeSchema,
  audio: SceneAudioSchema,
  video: SceneVideoSchema,
});
export type SceneNode = z.infer<typeof SceneNodeSchema>;

export const MasterManifestSchema = z
  .object({
    projectId: z.string().min(1),
    version: z.number().int().min(1),
    title: z.string().min(1),
    format: z.enum(["cinematic_drama", "documentary", "explainer", "podcast_clip", "vertical_short"]),
    contextArtifactIds: z.array(z.string()),
    globalStyle: z.object({
      aspectRatio: z.enum(["16:9", "9:16", "1:1"]),
      resolution: z.enum(["1080p", "4k"]),
      visualStylePrompt: z.string().min(1),
      colorGradingPreset: z.string().min(1),
      musicGenrePrompt: z.string().optional(),
    }),
    consistencies: z.object({
      characters: z.array(CharacterConsistencySchema),
      objects: z.array(ObjectConsistencySchema),
    }),
    scenes: z.array(SceneNodeSchema),
    outroEndFrame: z.object({
      prompt: z.string().min(1),
      selectedAssetUrl: z.string().nullable(),
      variants: z.array(z.string()),
      status: AssetStatusSchema,
    }),
    assembly: z.object({
      transitionType: z.enum(["cut", "crossfade", "dip_to_black"]),
      transitionDurationSec: z.number().min(0).max(5),
      backgroundMusicUrl: z.string().nullable(),
      burnCaptions: z.boolean(),
      subtitleStyle: z.enum(["subtitles_classic", "karaoke_active_word", "minimal_lower_third"]),
      thumbnail: z.object({
        prompt: z.string().min(1),
        selectedAssetUrl: z.string().nullable(),
        variants: z.array(z.string()),
        status: AssetStatusSchema,
      }),
      finalVideoUrl: z.string().nullable(),
      bundleZipUrl: z.string().nullable(),
      status: AssetStatusSchema,
      progressPercent: z.number().min(0).max(100),
    }),
  })
  .superRefine((manifest, ctx) => {
    const charIds = new Set(manifest.consistencies.characters.map((c) => c.id));
    const objIds = new Set(manifest.consistencies.objects.map((o) => o.id));
    const allRefIds = new Set([...charIds, ...objIds]);

    manifest.scenes.forEach((scene, sceneIdx) => {
      scene.keyframe.refIds.forEach((refId, refIdx) => {
        if (!allRefIds.has(refId)) {
          ctx.addIssue({
            code: z.ZodIssueCode.custom,
            message: `Scene '${scene.id}' keyframe references unknown refId '${refId}'`,
            path: ["scenes", sceneIdx, "keyframe", "refIds", refIdx],
          });
        }
      });

      scene.audio.dialogue.forEach((dlg, dlgIdx) => {
        if (!charIds.has(dlg.speakerId)) {
          ctx.addIssue({
            code: z.ZodIssueCode.custom,
            message: `Scene '${scene.id}' dialogue '${dlg.id}' references unknown speakerId '${dlg.speakerId}'`,
            path: ["scenes", sceneIdx, "audio", "dialogue", dlgIdx, "speakerId"],
          });
        }
      });
    });
  });

export type MasterManifest = z.infer<typeof MasterManifestSchema>;
