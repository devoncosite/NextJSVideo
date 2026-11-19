'use client';

import React, { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Sparkles, Loader2, ArrowRight } from 'lucide-react';
import { useStudioStore } from '@/store/studioStore';
import { useProjectSocket } from '@/hooks/useProjectSocket';
import { PitchCard, StoryPitchData } from '@/components/studio/planner/PitchCard';
import { BlueprintEditor } from '@/components/studio/planner/BlueprintEditor';

export default function Stage1PlannerPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = params?.projectId as string;

  const { manifest, fetchManifest, isGenerating, setGenerating, setActiveStage } =
    useStudioStore();

  useProjectSocket({ projectId });

  const [prompt, setPrompt] = useState(
    'A solitary radio astronomer in coastal Oregon intercepts an anomalous repeating signal.'
  );
  const [formatType, setFormatType] = useState('cinematic_drama');
  const [pitches, setPitches] = useState<StoryPitchData[]>([]);
  const [selectedPitchIndex, setSelectedPitchIndex] = useState<number>(1);
  const [isLoadingPitches, setIsLoadingPitches] = useState(false);
  const [isExpanding, setIsExpanding] = useState(false);

  useEffect(() => {
    setActiveStage(1);
    if (projectId && !manifest) {
      fetchManifest(projectId);
    }
  }, [projectId, manifest, fetchManifest, setActiveStage]);

  const handleGeneratePitches = async () => {
    if (!prompt.trim() || !projectId) return;
    setIsLoadingPitches(true);
    try {
      const res = await fetch(`/api/v1/projects/${projectId}/pipeline/pitches`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt, format_type: formatType }),
      });
      if (!res.ok) throw new Error('Failed to generate story pitches');
      const data: StoryPitchData[] = await res.json();
      setPitches(data);
      if (data.length > 0) {
        setSelectedPitchIndex(data[0].pitch_id);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setIsLoadingPitches(false);
    }
  };

  const handleSelectPitchAndExpand = async () => {
    if (!projectId) return;
    setIsExpanding(true);
    setGenerating(true);
    try {
      const res = await fetch(`/api/v1/projects/${projectId}/pipeline/planner`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          pitch_index: selectedPitchIndex,
          user_prompt: prompt,
          format_type: formatType,
        }),
      });
      if (!res.ok) throw new Error('Failed to expand pitch blueprint');
      await fetchManifest(projectId);
    } catch (err) {
      console.error(err);
    } finally {
      setIsExpanding(false);
      setGenerating(false);
    }
  };

  const handleProceedToStage2 = () => {
    router.push(`/studio/${projectId}/stage-2-consistencies`);
  };

  return (
    <div className="flex flex-col min-h-screen bg-black text-white p-8 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col gap-1 mb-8">
        <div className="flex items-center gap-2 text-xs font-bold text-emerald-400 uppercase tracking-widest">
          <span>Stage 1 of 7</span>
          <span>•</span>
          <span>Ideation & Script Blueprint</span>
        </div>
        <h1 className="text-3xl font-black text-zinc-100 tracking-tight">
          Planner & Story Pitcher
        </h1>
        <p className="text-sm text-zinc-400">
          Transform conceptual topics and ingested documents into structured narrative pitches.
        </p>
      </div>

      {/* Input Formulation Card */}
      <div className="flex flex-col gap-4 p-6 bg-zinc-950 border border-zinc-800 rounded-2xl shadow-xl">
        <div className="flex flex-col md:flex-row gap-4 items-start justify-between">
          <div className="flex-1 w-full flex flex-col gap-2">
            <label className="text-xs font-semibold text-zinc-300 uppercase tracking-wider">
              Topic or Narrative Prompt
            </label>
            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              className="w-full h-24 p-3 bg-zinc-900 border border-zinc-700 rounded-xl text-sm text-zinc-100 focus:outline-none focus:border-emerald-500 transition-colors"
              placeholder="Describe your story, topic, or narrative intent..."
            />
          </div>

          <div className="w-full md:w-64 flex flex-col gap-2">
            <label className="text-xs font-semibold text-zinc-300 uppercase tracking-wider">
              Format Presets
            </label>
            <select
              value={formatType}
              onChange={(e) => setFormatType(e.target.value)}
              className="w-full p-3 bg-zinc-900 border border-zinc-700 rounded-xl text-sm text-zinc-200 focus:outline-none focus:border-emerald-500"
            >
              <option value="cinematic_drama">Cinematic Drama (16:9)</option>
              <option value="educational_explainer">Educational Explainer (16:9)</option>
              <option value="vertical_short">Vertical Short (9:16)</option>
              <option value="podcast_clip">Podcast Clip (16:9)</option>
            </select>
          </div>
        </div>

        <div className="flex justify-end pt-2">
          <button
            type="button"
            onClick={handleGeneratePitches}
            disabled={isLoadingPitches || !prompt.trim()}
            className="px-6 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white font-semibold text-xs flex items-center gap-2 shadow-lg shadow-emerald-950/40 transition-all"
          >
            {isLoadingPitches ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" /> Generating 3 Pitch Angles...
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4" /> Synthesize Story Pitches
              </>
            )}
          </button>
        </div>
      </div>

      {/* Pitches Grid */}
      {pitches.length > 0 && (
        <div className="flex flex-col gap-4 mt-8">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold text-zinc-300 uppercase tracking-wider">
              Choose Story Pitch Angle
            </h2>
            <button
              type="button"
              onClick={handleSelectPitchAndExpand}
              disabled={isExpanding}
              className="px-5 py-2 rounded-lg bg-sky-600 hover:bg-sky-500 disabled:opacity-50 text-white font-semibold text-xs flex items-center gap-2 shadow-lg shadow-sky-950/40 transition-colors"
            >
              {isExpanding ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" /> Expanding Pitch into Blueprint...
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4" /> Expand Pitch #{selectedPitchIndex} into Blueprint
                </>
              )}
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            {pitches.map((p) => (
              <PitchCard
                key={p.pitch_id}
                pitch={p}
                isSelected={selectedPitchIndex === p.pitch_id}
                onSelect={() => setSelectedPitchIndex(p.pitch_id)}
              />
            ))}
          </div>
        </div>
      )}

      {/* Blueprint Table */}
      <BlueprintEditor onProceed={handleProceedToStage2} />
    </div>
  );
}
