import { describe, it, expect } from 'vitest';
import { applyJsonPatches, PatchOperation } from '../src/lib/patch';

describe('RFC 6902 JSON Patch Engine (Frontend)', () => {
  const initialManifest = {
    projectId: 'proj-123',
    version: 1,
    title: 'Cyberpunk Odyssey',
    scenes: [
      {
        id: 'scene-1',
        title: 'Opening Neon Shot',
        keyframe: {
          status: 'idle',
          progressPercent: 0,
          selectedAssetUrl: null,
          variants: [],
        },
        video: {
          status: 'idle',
          progressPercent: 0,
          rawVideoUrl: null,
        },
      },
    ],
    consistencies: {
      characters: [
        {
          id: 'char-1',
          name: 'Kaelen',
          turnaroundSheetUrl: null,
          status: 'idle',
        },
      ],
      objects: [],
    },
  };

  it('correctly applies replace patch to nested object fields', () => {
    const patches: PatchOperation[] = [
      { op: 'replace', path: '/scenes/0/keyframe/status', value: 'generating' },
      { op: 'replace', path: '/scenes/0/keyframe/progressPercent', value: 45 },
    ];

    const updated = applyJsonPatches(initialManifest, patches);

    expect(updated.scenes[0].keyframe.status).toBe('generating');
    expect(updated.scenes[0].keyframe.progressPercent).toBe(45);
    // Immutability check
    expect(initialManifest.scenes[0].keyframe.status).toBe('idle');
  });

  it('correctly applies add patch to array', () => {
    const patches: PatchOperation[] = [
      {
        op: 'add',
        path: '/consistencies/characters/1',
        value: {
          id: 'char-2',
          name: 'Mira',
          turnaroundSheetUrl: null,
          status: 'idle',
        },
      },
    ];

    const updated = applyJsonPatches(initialManifest, patches);

    expect(updated.consistencies.characters.length).toBe(2);
    expect(updated.consistencies.characters[1].name).toBe('Mira');
    expect(initialManifest.consistencies.characters.length).toBe(1);
  });

  it('correctly applies remove patch from array', () => {
    const patches: PatchOperation[] = [
      { op: 'remove', path: '/consistencies/characters/0' },
    ];

    const updated = applyJsonPatches(initialManifest, patches);

    expect(updated.consistencies.characters.length).toBe(0);
    expect(initialManifest.consistencies.characters.length).toBe(1);
  });

  it('handles root document replacement gracefully', () => {
    const newDoc = {
      ...initialManifest,
      title: 'Updated Odyssey',
      version: 2,
    };

    const patches: PatchOperation[] = [
      { op: 'replace', path: '/', value: newDoc },
    ];

    const updated = applyJsonPatches(initialManifest, patches);

    expect(updated.title).toBe('Updated Odyssey');
    expect(updated.version).toBe(2);
  });
});
