import { describe, it, expect, beforeEach } from 'vitest';
import { useStudioStore } from '../src/store/studioStore';
import { MasterManifest } from '../src/types/manifest';

describe('Zustand Master Studio Store', () => {
  const sampleManifest = {
    projectId: 'proj-zustand-101',
    version: 1,
    title: 'Neon Odyssey',
    format: 'cinematic_drama',
    contextArtifactIds: [],
    globalStyle: {
      aspectRatio: '16:9',
      resolution: '1080p',
      visualStylePrompt: 'Moody cinematic lighting',
      colorPalette: 'Neon teal and magenta',
      lighting: 'Volumetric',
    },
    scenes: [
      {
        id: 'scene-01',
        title: 'Cyber City Rain',
        sceneNumber: 1,
        timestamp: { startSec: 0, endSec: 5 },
        visualDescription: 'A rain-slicked neon street',
        camera: { angle: 'low', movement: 'dolly', lens: '35mm' },
        keyframe: {
          status: 'idle',
          prompt: 'A cyberpunk street under rainy skies',
          selectedAssetUrl: null,
          variants: [],
          progressPercent: 0,
          refIds: [],
          aspectRatio: '16:9',
        },
        video: {
          status: 'idle',
          model: 'kling_v3',
          supportsNativeAudio: true,
          durationSec: 5,
          requiresLipSync: false,
          motionPrompt: 'Slow dolly forward',
          rawVideoUrl: null,
          lipSyncedVideoUrl: null,
          progressPercent: 0,
        },
        audio: {
          status: 'idle',
          mergedSceneAudioUrl: null,
          voiceover: {
            status: 'idle',
            voiceId: 'v1',
            startOffsetSec: 0,
            text: 'Hello world',
            speed: 1.0,
            volume: 1.0,
            assetUrl: null,
            provider: 'elevenlabs',
          },
          dialogue: [],
          sfx: { status: 'idle', tracks: [] },
        },
      },
    ],
    consistencies: {
      characters: [
        {
          id: 'char-01',
          name: 'Ren',
          role: 'protagonist',
          description: 'A rogue cybernetic engineer',
          prompt360: 'Full 360 turnaround sheet',
          status: 'idle',
          variants: [],
          selectedTurnaroundUrl: null,
          views: { front: null, side34: null, profile: null, back: null },
        },
      ],
      objects: [],
    },
    assembly: {
      status: 'idle',
      progressPercent: 0,
      backgroundMusic: {
        status: 'idle',
        prompt: 'Synthwave',
        volume: 0.3,
        duckingAmountDb: 12,
        assetUrl: null,
      },
      subtitles: {
        enabled: true,
        style: 'karaoke',
        font: 'Inter',
        fontSize: 24,
        primaryColor: '#ffffff',
        highlightColor: '#ff0055',
        assFileUrl: null,
      },
      youtubeThumbnail: {
        status: 'idle',
        prompt: 'Eye-catching thumbnail',
        selectedAssetUrl: null,
        variants: [],
      },
      finalVideoUrl: null,
      bundleZipUrl: null,
    },
  } as unknown as MasterManifest;

  beforeEach(() => {
    useStudioStore.setState({
      manifest: null,
      activeStage: 1,
      selectedSceneId: null,
      isGenerating: false,
      connectionState: 'disconnected',
      version: 1,
      error: null,
    });
  });

  it('sets manifest and initializes default scene and version', () => {
    const store = useStudioStore.getState();
    store.setManifest(sampleManifest);

    const updated = useStudioStore.getState();
    expect(updated.manifest).not.toBeNull();
    expect(updated.manifest?.projectId).toBe('proj-zustand-101');
    expect(updated.version).toBe(1);
    expect(updated.selectedSceneId).toBe('scene-01');
  });

  it('switches active pipeline stage', () => {
    const store = useStudioStore.getState();
    expect(store.activeStage).toBe(1);

    store.setActiveStage(3);
    expect(useStudioStore.getState().activeStage).toBe(3);

    store.setActiveStage(6);
    expect(useStudioStore.getState().activeStage).toBe(6);
  });

  it('applies real-time WebSocket patch delta and increments version', () => {
    const store = useStudioStore.getState();
    store.setManifest(sampleManifest);

    store.applyPatchDelta(2, [
      { op: 'replace', path: '/scenes/0/keyframe/status', value: 'generating' },
      { op: 'replace', path: '/scenes/0/keyframe/progressPercent', value: 75 },
    ]);

    const updated = useStudioStore.getState();
    expect(updated.version).toBe(2);
    expect(updated.manifest?.scenes[0].keyframe.status).toBe('generating');
    expect(updated.manifest?.scenes[0].keyframe.progressPercent).toBe(75);
  });

  it('optimistically updates prompt via updatePrompt action', () => {
    const store = useStudioStore.getState();
    store.setManifest(sampleManifest);

    store.updatePrompt('/scenes/0/keyframe/prompt', 'Updated neon street view');

    const updated = useStudioStore.getState();
    expect(updated.manifest?.scenes[0].keyframe.prompt).toBe('Updated neon street view');
    expect(updated.version).toBe(2);
  });

  it('selects asset variant and updates selectedAssetUrl', () => {
    const store = useStudioStore.getState();
    store.setManifest(sampleManifest);

    store.selectVariant(
      '/scenes/0/keyframe/selectedAssetUrl',
      'https://storage.cineforge.ai/assets/kf_selected.png'
    );

    const updated = useStudioStore.getState();
    expect(updated.manifest?.scenes[0].keyframe.selectedAssetUrl).toBe(
      'https://storage.cineforge.ai/assets/kf_selected.png'
    );
  });
});
