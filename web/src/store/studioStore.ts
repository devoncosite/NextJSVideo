import { create } from 'zustand';
import { MasterManifest } from '@/types/manifest';
import { PatchOperation, applyJsonPatches } from '@/lib/patch';

export interface StudioState {
  manifest: MasterManifest | null;
  activeStage: number; // 1 to 7
  selectedSceneId: string | null;
  isGenerating: boolean;
  connectionState: 'connected' | 'connecting' | 'disconnected' | 'error';
  version: number;
  error: string | null;

  // Actions
  setManifest: (manifest: MasterManifest) => void;
  setActiveStage: (stage: number) => void;
  setSelectedSceneId: (id: string | null) => void;
  setGenerating: (isGenerating: boolean) => void;
  setConnectionState: (state: 'connected' | 'connecting' | 'disconnected' | 'error') => void;
  setError: (error: string | null) => void;
  applyPatchDelta: (version: number, patches: PatchOperation[]) => void;
  updatePrompt: (path: string, prompt: string) => void;
  selectVariant: (path: string, variantUrl: string) => void;
  fetchManifest: (projectId: string) => Promise<void>;
}

export const useStudioStore = create<StudioState>((set, get) => ({
  manifest: null,
  activeStage: 1,
  selectedSceneId: null,
  isGenerating: false,
  connectionState: 'disconnected',
  version: 1,
  error: null,

  setManifest: (manifest: MasterManifest) =>
    set({
      manifest,
      version: manifest.version ?? 1,
      selectedSceneId: manifest.scenes?.[0]?.id ?? null,
      error: null,
    }),

  setActiveStage: (stage: number) => set({ activeStage: stage }),

  setSelectedSceneId: (id: string | null) => set({ selectedSceneId: id }),

  setGenerating: (isGenerating: boolean) => set({ isGenerating }),

  setConnectionState: (connectionState) => set({ connectionState }),

  setError: (error: string | null) => set({ error }),

  applyPatchDelta: (version: number, patches: PatchOperation[]) => {
    const current = get().manifest;
    if (!current) return;

    try {
      const updated = applyJsonPatches(current, patches);
      set({
        manifest: updated,
        version,
        error: null,
      });
    } catch (err: any) {
      console.error('Failed to apply patch delta in Zustand store:', err);
      set({ error: err?.message || 'Error updating studio state' });
    }
  },

  updatePrompt: (path: string, prompt: string) => {
    const { applyPatchDelta, version } = get();
    applyPatchDelta(version + 1, [
      {
        op: 'replace',
        path,
        value: prompt,
      },
    ]);
  },

  selectVariant: (path: string, variantUrl: string) => {
    const { applyPatchDelta, version } = get();
    applyPatchDelta(version + 1, [
      {
        op: 'replace',
        path,
        value: variantUrl,
      },
    ]);
  },

  fetchManifest: async (projectId: string) => {
    try {
      set({ connectionState: 'connecting' });
      const res = await fetch(`/api/v1/projects/${projectId}`);
      if (!res.ok) {
        throw new Error(`Failed to load project manifest: HTTP ${res.status}`);
      }
      const data = await res.json();
      if (data.manifest) {
        get().setManifest(data.manifest);
        set({ connectionState: 'connected' });
      }
    } catch (err: any) {
      console.error('Error fetching manifest:', err);
      set({ error: err.message, connectionState: 'error' });
    }
  },
}));
