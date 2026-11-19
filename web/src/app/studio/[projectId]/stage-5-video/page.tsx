'use client';

import React, { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Film, Sparkles, Loader2, ArrowRight, ArrowLeft } from 'lucide-react';
import { useStudioStore } from '@/store/studioStore';
import { useProjectSocket } from '@/hooks/useProjectSocket';
import { GenerationCard } from '@/components/studio/cards/GenerationCard';
import { LipSyncCompare } from '@/components/studio/video/LipSyncCompare';

export default function Stage5VideoPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = params?.projectId as string;

  const {
    manifest,
    fetchManifest,
    updatePrompt,
    isGenerating,
    setGenerating,
    setActiveStage,
  } = useStudioStore();

  useProjectSocket({ projectId });

  const [isDispatching, setIsDispatching] = useState(false);
  const [activeCompareSceneIdx, setActiveCompareSceneIdx] = useState<number | null>(null);

  useEffect(() => {
    setActiveStage(5);
    if (projectId && !manifest) {
      fetchManifest(projectId);
    }
  }, [projectId, manifest, fetchManifest, setActiveStage]);

  const handleGenerateVideo = async () => {
    if (!projectId) return;
    setIsDispatching(true);
    setGenerating(true);
    try {
      const res = await fetch(`/api/v1/projects/${projectId}/pipeline/video`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      });
      if (!res.ok) throw new Error('Failed to dispatch video generation batch');
      await fetchManifest(projectId);
    } catch (err) {
      console.error(err);
    } finally {
      setIsDispatching(false);
      setGenerating(false);
    }
  };

  const scenes = manifest?.scenes || [];

  return (
    <div className="flex flex-col min-h-screen bg-black text-white p-8 max-w-7xl mx-auto">
      {/* Stage Header */}
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 mb-8">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2 text-xs font-bold text-emerald-400 uppercase tracking-widest">
            <span>Stage 5 of 7</span>
            <span>•</span>
            <span>Visual Scene Video & Lip-Sync</span>
          </div>
          <h1 className="text-3xl font-black text-zinc-100 tracking-tight">
            Kling / LTX-Video & SyncLabs Lip-Sync Routing
          </h1>
          <p className="text-sm text-zinc-400">
            Generate video clips conditioned between start and end frames with automated neural lip-syncing.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => router.push(`/studio/${projectId}/stage-4-audio`)}
            className="px-4 py-2 rounded-lg bg-zinc-900 hover:bg-zinc-800 text-zinc-300 font-medium text-xs flex items-center gap-1.5 border border-zinc-800 transition-colors"
          >
            <ArrowLeft className="w-3.5 h-3.5" /> Back to Stage 4
          </button>

          <button
            type="button"
            onClick={handleGenerateVideo}
            disabled={isDispatching || isGenerating}
            className="px-5 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white font-semibold text-xs flex items-center gap-2 shadow-lg shadow-emerald-950/40 transition-all"
          >
            {isDispatching ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" /> Rendering Video Clips...
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4" /> Generate All Video Clips
              </>
            )}
          </button>

          <button
            type="button"
            onClick={() => router.push(`/studio/${projectId}`)}
            className="px-5 py-2.5 rounded-xl bg-sky-600 hover:bg-sky-500 text-white font-semibold text-xs flex items-center gap-2 shadow-lg shadow-sky-950/40 transition-colors"
          >
            Proceed to Stage 6 Assembly <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Video Generation Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
        {scenes.map((scene, idx) => {
          const vidUrl = scene.video.lipSyncedVideoUrl || scene.video.rawVideoUrl;
          const hasLipSync = scene.video.requiresLipSync;

          return (
            <div key={scene.id} className="flex flex-col gap-3">
              <GenerationCard
                title={`Scene #${scene.sceneNumber}: Motion Video`}
                badgeText={`${scene.timestamp.startSec}s - ${scene.timestamp.endSec}s`}
                status={scene.video.status}
                progressPercent={scene.video.progressPercent}
                prompt={scene.video.motionPrompt}
                selectedAssetUrl={vidUrl}
                mediaType="video"
                aspectRatio="16:9"
                onPromptChange={(newPrompt) =>
                  updatePrompt(`/scenes/${idx}/video/motionPrompt`, newPrompt)
                }
                onRegenerate={handleGenerateVideo}
              />

              {hasLipSync && scene.video.rawVideoUrl && scene.video.lipSyncedVideoUrl && (
                <button
                  type="button"
                  onClick={() =>
                    setActiveCompareSceneIdx(activeCompareSceneIdx === idx ? null : idx)
                  }
                  className="px-3 py-1.5 rounded-lg bg-zinc-900 border border-zinc-700 hover:border-emerald-500 text-zinc-300 text-xs font-semibold flex items-center justify-center gap-1.5 transition-colors"
                >
                  {activeCompareSceneIdx === idx
                    ? 'Hide Lip-Sync Comparison'
                    : 'Open Lip-Sync Split Comparison'}
                </button>
              )}

              {activeCompareSceneIdx === idx && (
                <LipSyncCompare
                  rawVideoUrl={scene.video.rawVideoUrl}
                  lipSyncedVideoUrl={scene.video.lipSyncedVideoUrl}
                  sceneNumber={scene.sceneNumber}
                />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
