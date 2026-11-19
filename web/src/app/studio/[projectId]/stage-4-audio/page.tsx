'use client';

import React, { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Volume2, Sparkles, Loader2, ArrowRight, ArrowLeft, Mic } from 'lucide-react';
import { useStudioStore } from '@/store/studioStore';
import { useProjectSocket } from '@/hooks/useProjectSocket';
import { WaveformTrack } from '@/components/studio/audio/WaveformTrack';

export default function Stage4AudioPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = params?.projectId as string;

  const {
    manifest,
    fetchManifest,
    selectedSceneId,
    setSelectedSceneId,
    isGenerating,
    setGenerating,
    setActiveStage,
  } = useStudioStore();

  useProjectSocket({ projectId });

  const [isDispatching, setIsDispatching] = useState(false);

  useEffect(() => {
    setActiveStage(4);
    if (projectId && !manifest) {
      fetchManifest(projectId);
    }
  }, [projectId, manifest, fetchManifest, setActiveStage]);

  const handleSynthesizeAudio = async () => {
    if (!projectId) return;
    setIsDispatching(true);
    setGenerating(true);
    try {
      const res = await fetch(`/api/v1/projects/${projectId}/pipeline/audio`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      });
      if (!res.ok) throw new Error('Failed to dispatch audio synthesis batch');
      await fetchManifest(projectId);
    } catch (err) {
      console.error(err);
    } finally {
      setIsDispatching(false);
      setGenerating(false);
    }
  };

  const scenes = manifest?.scenes || [];
  const activeSceneIndex = Math.max(
    0,
    scenes.findIndex((s) => s.id === selectedSceneId)
  );
  const activeScene = scenes[activeSceneIndex] || scenes[0];

  const sceneDuration = activeScene
    ? activeScene.timestamp.endSec - activeScene.timestamp.startSec
    : 5.0;

  return (
    <div className="flex flex-col min-h-screen bg-black text-white p-8 max-w-7xl mx-auto">
      {/* Stage Header */}
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 mb-8">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2 text-xs font-bold text-emerald-400 uppercase tracking-widest">
            <span>Stage 4 of 7</span>
            <span>•</span>
            <span>Multi-Track Audio & Speech Synthesis</span>
          </div>
          <h1 className="text-3xl font-black text-zinc-100 tracking-tight">
            ElevenLabs TTS & FFmpeg Spatial Audio Mixer
          </h1>
          <p className="text-sm text-zinc-400">
            Synthesize word-aligned dialogue, narration, and composite per-scene master audio tracks.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => router.push(`/studio/${projectId}/stage-3-keyframes`)}
            className="px-4 py-2 rounded-lg bg-zinc-900 hover:bg-zinc-800 text-zinc-300 font-medium text-xs flex items-center gap-1.5 border border-zinc-800 transition-colors"
          >
            <ArrowLeft className="w-3.5 h-3.5" /> Back to Stage 3
          </button>

          <button
            type="button"
            onClick={handleSynthesizeAudio}
            disabled={isDispatching || isGenerating}
            className="px-5 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white font-semibold text-xs flex items-center gap-2 shadow-lg shadow-emerald-950/40 transition-all"
          >
            {isDispatching ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" /> Mixing Multi-Track Audio...
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4" /> Synthesize & Mix All Audio
              </>
            )}
          </button>

          <button
            type="button"
            onClick={() => router.push(`/studio/${projectId}/stage-5-video`)}
            className="px-5 py-2.5 rounded-xl bg-sky-600 hover:bg-sky-500 text-white font-semibold text-xs flex items-center gap-2 shadow-lg shadow-sky-950/40 transition-colors"
          >
            Proceed to Stage 5 <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Scene Selector Pills */}
      <div className="flex items-center gap-2 overflow-x-auto pb-3 mb-6 border-b border-zinc-800">
        {scenes.map((scene, idx) => {
          const isSelected = activeScene?.id === scene.id;
          const hasAudio = !!scene.audio.mergedSceneAudioUrl;

          return (
            <button
              key={scene.id}
              type="button"
              onClick={() => setSelectedSceneId(scene.id)}
              className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold transition-all ${
                isSelected
                  ? 'bg-zinc-800 text-emerald-400 border border-zinc-700 shadow-md'
                  : 'bg-zinc-950 text-zinc-400 border border-zinc-900 hover:border-zinc-800'
              }`}
            >
              <span>Scene #{scene.sceneNumber}</span>
              <span className="text-[10px] text-zinc-500 font-mono">
                ({scene.timestamp.startSec}s - {scene.timestamp.endSec}s)
              </span>
              {hasAudio && (
                <span className="w-2 h-2 rounded-full bg-emerald-500" title="Audio ready" />
              )}
            </button>
          );
        })}
      </div>

      {/* Active Scene Audio Canvas */}
      {activeScene ? (
        <div className="flex flex-col gap-6 p-6 bg-zinc-950 border border-zinc-800 rounded-2xl shadow-xl">
          <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
            <div>
              <h2 className="text-base font-bold text-zinc-200">
                Scene #{activeScene.sceneNumber} Multi-Track Workspace
              </h2>
              <span className="text-xs text-zinc-500 font-mono">
                Duration: {sceneDuration.toFixed(1)} seconds
              </span>
            </div>

            {/* Merged Scene Audio Status */}
            {activeScene.audio.mergedSceneAudioUrl ? (
              <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-950/60 border border-emerald-800/60 text-emerald-300 text-xs font-semibold">
                <Volume2 className="w-3.5 h-3.5" />
                <span>Scene Mix Ready</span>
              </div>
            ) : (
              <span className="text-xs text-zinc-500 italic">Not yet composited</span>
            )}
          </div>

          {/* Track 1: Voiceover */}
          <div className="flex flex-col gap-2">
            <span className="text-xs font-bold uppercase tracking-wider text-sky-400">
              Track 1: Narration & Voiceover
            </span>
            {activeScene.audio.voiceover?.enabled ? (
              <WaveformTrack
                label="Voiceover"
                text={activeScene.audio.voiceover.text}
                audioUrl={activeScene.audio.voiceover.assetUrl}
                startOffsetSec={activeScene.audio.voiceover.startOffsetSec}
                endOffsetSec={activeScene.audio.voiceover.endOffsetSec}
                totalDurationSec={sceneDuration}
                waveColor="#38bdf8"
                progressColor="#0284c7"
              />
            ) : (
              <div className="p-4 rounded-xl bg-zinc-900/40 border border-zinc-800/80 text-xs text-zinc-500 italic">
                Voiceover narration is disabled for this scene.
              </div>
            )}
          </div>

          {/* Track 2: Dialogue Lines */}
          <div className="flex flex-col gap-2">
            <span className="text-xs font-bold uppercase tracking-wider text-emerald-400">
              Track 2: Character Dialogue ({activeScene.audio.dialogue?.length || 0} Lines)
            </span>
            {activeScene.audio.dialogue && activeScene.audio.dialogue.length > 0 ? (
              <div className="flex flex-col gap-3">
                {activeScene.audio.dialogue.map((dlg, dIdx) => (
                  <WaveformTrack
                    key={dlg.id || dIdx}
                    label={`Dialogue #${dIdx + 1}`}
                    speaker={dlg.speakerId}
                    text={dlg.text}
                    audioUrl={dlg.assetUrl}
                    startOffsetSec={dlg.startOffsetSec}
                    endOffsetSec={dlg.endOffsetSec}
                    totalDurationSec={sceneDuration}
                    waveColor="#10b981"
                    progressColor="#059669"
                  />
                ))}
              </div>
            ) : (
              <div className="p-4 rounded-xl bg-zinc-900/40 border border-zinc-800/80 text-xs text-zinc-500 italic">
                No dialogue lines scripted for this scene.
              </div>
            )}
          </div>

          {/* Track 3: Per-Scene Master Audio Result */}
          {activeScene.audio.mergedSceneAudioUrl && (
            <div className="flex flex-col gap-2 pt-4 border-t border-zinc-800">
              <span className="text-xs font-bold uppercase tracking-wider text-amber-400">
                Master Scene Mix (EBU R128 Loudness Normalized)
              </span>
              <WaveformTrack
                label="Master Scene M4A"
                text="Composite audio stream"
                audioUrl={activeScene.audio.mergedSceneAudioUrl}
                startOffsetSec={0}
                endOffsetSec={sceneDuration}
                totalDurationSec={sceneDuration}
                waveColor="#f59e0b"
                progressColor="#d97706"
              />
            </div>
          )}
        </div>
      ) : (
        <div className="p-12 text-center text-zinc-500">Loading scene audio timeline...</div>
      )}
    </div>
  );
}
