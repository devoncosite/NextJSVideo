'use client';

import React, { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Users, Box, Sparkles, Loader2, ArrowRight, ArrowLeft } from 'lucide-react';
import { useStudioStore } from '@/store/studioStore';
import { useProjectSocket } from '@/hooks/useProjectSocket';
import { GenerationCard } from '@/components/studio/cards/GenerationCard';
import { TurnaroundViewer } from '@/components/studio/consistencies/TurnaroundViewer';

export default function Stage2ConsistenciesPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = params?.projectId as string;

  const {
    manifest,
    fetchManifest,
    selectVariant,
    updatePrompt,
    isGenerating,
    setGenerating,
    setActiveStage,
  } = useStudioStore();

  useProjectSocket({ projectId });

  const [activeTab, setActiveTab] = useState<'characters' | 'objects'>('characters');
  const [isDispatching, setIsDispatching] = useState(false);

  useEffect(() => {
    setActiveStage(2);
    if (projectId && !manifest) {
      fetchManifest(projectId);
    }
  }, [projectId, manifest, fetchManifest, setActiveStage]);

  const handleGenerateAll = async () => {
    if (!projectId) return;
    setIsDispatching(true);
    setGenerating(true);
    try {
      const res = await fetch(`/api/v1/projects/${projectId}/pipeline/consistencies`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      });
      if (!res.ok) throw new Error('Failed to dispatch consistency batch');
      await fetchManifest(projectId);
    } catch (err) {
      console.error(err);
    } finally {
      setIsDispatching(false);
      setGenerating(false);
    }
  };

  const characters = manifest?.consistencies?.characters || [];
  const objects = manifest?.consistencies?.objects || [];

  return (
    <div className="flex flex-col min-h-screen bg-black text-white p-8 max-w-7xl mx-auto">
      {/* Stage Header */}
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 mb-8">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2 text-xs font-bold text-emerald-400 uppercase tracking-widest">
            <span>Stage 2 of 7</span>
            <span>•</span>
            <span>360° Visual Consistencies</span>
          </div>
          <h1 className="text-3xl font-black text-zinc-100 tracking-tight">
            Character & Object Turnaround Engine
          </h1>
          <p className="text-sm text-zinc-400">
            Generate 360° model sheets to establish locked visual anchors for all subsequent scenes.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => router.push(`/studio/${projectId}/stage-1-planner`)}
            className="px-4 py-2 rounded-lg bg-zinc-900 hover:bg-zinc-800 text-zinc-300 font-medium text-xs flex items-center gap-1.5 border border-zinc-800 transition-colors"
          >
            <ArrowLeft className="w-3.5 h-3.5" /> Back to Stage 1
          </button>

          <button
            type="button"
            onClick={handleGenerateAll}
            disabled={isDispatching || isGenerating}
            className="px-5 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white font-semibold text-xs flex items-center gap-2 shadow-lg shadow-emerald-950/40 transition-all"
          >
            {isDispatching ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" /> Dispatching Batch...
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4" /> Generate All 360° Sheets
              </>
            )}
          </button>

          <button
            type="button"
            onClick={() => router.push(`/studio/${projectId}/stage-3-keyframes`)}
            className="px-5 py-2.5 rounded-xl bg-sky-600 hover:bg-sky-500 text-white font-semibold text-xs flex items-center gap-2 shadow-lg shadow-sky-950/40 transition-colors"
          >
            Proceed to Stage 3 <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-3 border-b border-zinc-800 pb-3 mb-6">
        <button
          type="button"
          onClick={() => setActiveTab('characters')}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold transition-all ${
            activeTab === 'characters'
              ? 'bg-zinc-800 text-emerald-400 border border-zinc-700 shadow-md'
              : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900'
          }`}
        >
          <Users className="w-4 h-4" />
          Characters ({characters.length})
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('objects')}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold transition-all ${
            activeTab === 'objects'
              ? 'bg-zinc-800 text-emerald-400 border border-zinc-700 shadow-md'
              : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900'
          }`}
        >
          <Box className="w-4 h-4" />
          Key Objects ({objects.length})
        </button>
      </div>

      {/* Grid of Cards */}
      {activeTab === 'characters' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {characters.map((char, idx) => (
            <div key={char.id} className="flex flex-col gap-3">
              <GenerationCard
                title={char.name}
                badgeText={char.role}
                status={char.status}
                progressPercent={char.progressPercent}
                prompt={char.prompt360}
                selectedAssetUrl={char.selectedAssetUrl}
                variants={char.variants}
                error={char.error}
                mediaType="image"
                aspectRatio="16:9"
                onPromptChange={(newPrompt) =>
                  updatePrompt(`/consistencies/characters/${idx}/prompt360`, newPrompt)
                }
                onSelectVariant={(url) =>
                  selectVariant(`/consistencies/characters/${idx}/selectedAssetUrl`, url)
                }
                onRegenerate={handleGenerateAll}
              />

              {char.variants && char.variants.length > 0 && (
                <TurnaroundViewer
                  name={char.name}
                  variants={char.variants}
                  selectedUrl={char.selectedAssetUrl}
                  onLockVariant={(url) =>
                    selectVariant(`/consistencies/characters/${idx}/selectedAssetUrl`, url)
                  }
                />
              )}
            </div>
          ))}
          {characters.length === 0 && (
            <div className="col-span-2 p-12 text-center text-zinc-500 border border-dashed border-zinc-800 rounded-xl">
              No character entities identified in this blueprint.
            </div>
          )}
        </div>
      )}

      {activeTab === 'objects' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {objects.map((obj, idx) => (
            <div key={obj.id} className="flex flex-col gap-3">
              <GenerationCard
                title={obj.name}
                badgeText={obj.category}
                status={obj.status}
                progressPercent={obj.progressPercent}
                prompt={obj.prompt360}
                selectedAssetUrl={obj.selectedAssetUrl}
                variants={obj.variants}
                error={obj.error}
                mediaType="image"
                aspectRatio="16:9"
                onPromptChange={(newPrompt) =>
                  updatePrompt(`/consistencies/objects/${idx}/prompt360`, newPrompt)
                }
                onSelectVariant={(url) =>
                  selectVariant(`/consistencies/objects/${idx}/selectedAssetUrl`, url)
                }
                onRegenerate={handleGenerateAll}
              />

              {obj.variants && obj.variants.length > 0 && (
                <TurnaroundViewer
                  name={obj.name}
                  variants={obj.variants}
                  selectedUrl={obj.selectedAssetUrl}
                  onLockVariant={(url) =>
                    selectVariant(`/consistencies/objects/${idx}/selectedAssetUrl`, url)
                  }
                />
              )}
            </div>
          ))}
          {objects.length === 0 && (
            <div className="col-span-2 p-12 text-center text-zinc-500 border border-dashed border-zinc-800 rounded-xl">
              No key object entities identified in this blueprint.
            </div>
          )}
        </div>
      )}
    </div>
  );
}
