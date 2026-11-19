'use client';

import React, { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Sparkles, Loader2, ArrowRight, ArrowLeft, Image as ImageIcon } from 'lucide-react';
import { useStudioStore } from '@/store/studioStore';
import { useProjectSocket } from '@/hooks/useProjectSocket';
import { GenerationCard } from '@/components/studio/cards/GenerationCard';
import { ChainingDiagram } from '@/components/studio/keyframes/ChainingDiagram';

export default function Stage3KeyframesPage() {
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

  const [isDispatching, setIsDispatching] = useState(false);

  useEffect(() => {
    setActiveStage(3);
    if (projectId && !manifest) {
      fetchManifest(projectId);
    }
  }, [projectId, manifest, fetchManifest, setActiveStage]);

  const handleGenerateKeyframes = async () => {
    if (!projectId) return;
    setIsDispatching(true);
    setGenerating(true);
    try {
      const res = await fetch(`/api/v1/projects/${projectId}/pipeline/keyframes`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      });
      if (!res.ok) throw new Error('Failed to dispatch keyframe batch');
      await fetchManifest(projectId);
    } catch (err) {
      console.error(err);
    } finally {
      setIsDispatching(false);
      setGenerating(false);
    }
  };

  const scenes = manifest?.scenes || [];
  const outroEndFrame = manifest?.outroEndFrame;

  // Lookup for reference avatar chips
  const charMap = new Map((manifest?.consistencies?.characters || []).map((c) => [c.id, c]));
  const objMap = new Map((manifest?.consistencies?.objects || []).map((o) => [o.id, o]));

  return (
    <div className="flex flex-col min-h-screen bg-black text-white p-8 max-w-7xl mx-auto">
      {/* Stage Header */}
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 mb-8">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2 text-xs font-bold text-emerald-400 uppercase tracking-widest">
            <span>Stage 3 of 7</span>
            <span>•</span>
            <span>Anchor Keyframes & Chaining</span>
          </div>
          <h1 className="text-3xl font-black text-zinc-100 tracking-tight">
            Reference Injection & Start/End Frames
          </h1>
          <p className="text-sm text-zinc-400">
            Synthesize scene start frames conditioned on locked character sheets and linked continuously.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => router.push(`/studio/${projectId}/stage-2-consistencies`)}
            className="px-4 py-2 rounded-lg bg-zinc-900 hover:bg-zinc-800 text-zinc-300 font-medium text-xs flex items-center gap-1.5 border border-zinc-800 transition-colors"
          >
            <ArrowLeft className="w-3.5 h-3.5" /> Back to Stage 2
          </button>

          <button
            type="button"
            onClick={handleGenerateKeyframes}
            disabled={isDispatching || isGenerating}
            className="px-5 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white font-semibold text-xs flex items-center gap-2 shadow-lg shadow-emerald-950/40 transition-all"
          >
            {isDispatching ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" /> Generating Keyframes...
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4" /> Generate All Scene Keyframes
              </>
            )}
          </button>

          <button
            type="button"
            onClick={() => router.push(`/studio/${projectId}/stage-4-audio`)}
            className="px-5 py-2.5 rounded-xl bg-sky-600 hover:bg-sky-500 text-white font-semibold text-xs flex items-center gap-2 shadow-lg shadow-sky-950/40 transition-colors"
          >
            Proceed to Stage 4 <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Chaining Topology Diagram */}
      <div className="mb-8">
        <ChainingDiagram scenes={scenes} outroEndFrame={outroEndFrame} />
      </div>

      {/* Keyframe Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {scenes.map((scene, idx) => {
          const refIds = scene.keyframe.refIds || [];

          return (
            <div key={scene.id} className="flex flex-col gap-2">
              <GenerationCard
                title={`Scene #${scene.sceneNumber}: Keyframe`}
                badgeText={`${scene.timestamp.startSec}s - ${scene.timestamp.endSec}s`}
                status={scene.keyframe.status}
                progressPercent={scene.keyframe.progressPercent}
                prompt={scene.keyframe.prompt}
                selectedAssetUrl={scene.keyframe.selectedAssetUrl}
                variants={scene.keyframe.variants}
                mediaType="image"
                aspectRatio="16:9"
                onPromptChange={(newPrompt) =>
                  updatePrompt(`/scenes/${idx}/keyframe/prompt`, newPrompt)
                }
                onSelectVariant={(url) =>
                  selectVariant(`/scenes/${idx}/keyframe/selectedAssetUrl`, url)
                }
                onRegenerate={handleGenerateKeyframes}
              />

              {/* Injected Reference Badges */}
              {refIds.length > 0 && (
                <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-zinc-950 border border-zinc-800 text-[11px] text-zinc-400">
                  <span className="text-zinc-500 font-semibold text-[10px] uppercase">Conditioned on:</span>
                  <div className="flex items-center gap-1 overflow-x-auto">
                    {refIds.map((rId) => {
                      const entity = charMap.get(rId) || objMap.get(rId);
                      return (
                        <span
                          key={rId}
                          className="px-2 py-0.5 rounded bg-zinc-900 border border-zinc-700 text-zinc-200 font-medium truncate max-w-[120px]"
                          title={entity?.name || rId}
                        >
                          {entity?.name || rId}
                        </span>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          );
        })}

        {/* Outro End Frame Card */}
        {outroEndFrame && (
          <div className="flex flex-col gap-2">
            <GenerationCard
              title="Outro End Frame (Closing Anchor)"
              badgeText="Final Scene End"
              status={outroEndFrame.status}
              progressPercent={100}
              prompt={outroEndFrame.prompt}
              selectedAssetUrl={outroEndFrame.selectedAssetUrl}
              variants={outroEndFrame.variants}
              mediaType="image"
              aspectRatio="16:9"
              onPromptChange={(newPrompt) =>
                updatePrompt(`/outroEndFrame/prompt`, newPrompt)
              }
              onSelectVariant={(url) =>
                selectVariant(`/outroEndFrame/selectedAssetUrl`, url)
              }
              onRegenerate={handleGenerateKeyframes}
            />
          </div>
        )}
      </div>
    </div>
  );
}
