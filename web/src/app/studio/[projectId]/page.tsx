'use client';

import React, { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import {
  Film,
  Sparkles,
  Download,
  Play,
  Volume2,
  CheckCircle2,
  Loader2,
  Image as ImageIcon,
  Layers,
  ArrowRight,
} from 'lucide-react';
import { useStudioStore } from '@/store/studioStore';
import { useProjectSocket } from '@/hooks/useProjectSocket';
import { ExportHubModal } from '@/components/studio/export/ExportHubModal';
import { VariantPicker } from '@/components/studio/cards/VariantPicker';

export default function StudioMasterPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = params?.projectId as string;

  const {
    manifest,
    fetchManifest,
    selectVariant,
    isGenerating,
    setGenerating,
    setActiveStage,
  } = useStudioStore();

  useProjectSocket({ projectId });

  const [isAssembling, setIsAssembling] = useState(false);
  const [isExportModalOpen, setIsExportModalOpen] = useState(false);
  const [burnCaptions, setBurnCaptions] = useState(true);

  useEffect(() => {
    setActiveStage(6);
    if (projectId && !manifest) {
      fetchManifest(projectId);
    }
  }, [projectId, manifest, fetchManifest, setActiveStage]);

  const handleRunAssembly = async () => {
    if (!projectId) return;
    setIsAssembling(true);
    setGenerating(true);
    try {
      const res = await fetch(`/api/v1/projects/${projectId}/pipeline/assembly`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ burn_captions: burnCaptions }),
      });
      if (!res.ok) throw new Error('Timeline assembly failed');
      await fetchManifest(projectId);
    } catch (err) {
      console.error(err);
    } finally {
      setIsAssembling(false);
      setGenerating(false);
    }
  };

  const handleExportZip = async (): Promise<string | null> => {
    if (!projectId) return null;
    const res = await fetch(`/api/v1/projects/${projectId}/pipeline/export`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ include_presets: true }),
    });
    if (!res.ok) throw new Error('ZIP packaging failed');
    const data = await res.json();
    await fetchManifest(projectId);
    return data.bundleZipUrl || null;
  };

  const assembly = manifest?.assembly;
  const thumbnail = assembly?.thumbnail;
  const finalVideoUrl = assembly?.finalVideoUrl;
  const bundleZipUrl = assembly?.bundleZipUrl;
  const scenes = manifest?.scenes || [];

  return (
    <div className="flex flex-col min-h-screen bg-black text-white p-8 max-w-7xl mx-auto">
      {/* Studio Header & Stepper */}
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 mb-8">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2 text-xs font-bold text-emerald-400 uppercase tracking-widest">
            <span>CineForge Studio Master</span>
            <span>•</span>
            <span>Version {manifest?.version || 1}</span>
          </div>
          <h1 className="text-3xl font-black text-zinc-100 tracking-tight">
            {manifest?.title || 'Production Studio'}
          </h1>
          <p className="text-sm text-zinc-400">
            Stages 6 & 7: Final timeline assembly, ASS subtitle burning, and multi-format packaging.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={handleRunAssembly}
            disabled={isAssembling || isGenerating}
            className="px-5 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white font-semibold text-xs flex items-center gap-2 shadow-lg shadow-emerald-950/40 transition-all"
          >
            {isAssembling ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" /> Assembling Master Video...
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4" /> Assemble Master Video
              </>
            )}
          </button>

          <button
            type="button"
            onClick={() => setIsExportModalOpen(true)}
            className="px-5 py-2.5 rounded-xl bg-sky-600 hover:bg-sky-500 text-white font-semibold text-xs flex items-center gap-2 shadow-lg shadow-sky-950/40 transition-colors"
          >
            <Download className="w-4 h-4" /> Export & Delivery Hub
          </button>
        </div>
      </div>

      {/* Stage Stepper Breadcrumb Bar */}
      <div className="flex items-center gap-2 overflow-x-auto pb-4 mb-8 border-b border-zinc-800 text-xs">
        {[
          { num: 1, label: 'Planner', path: 'stage-1-planner' },
          { num: 2, label: 'Consistencies', path: 'stage-2-consistencies' },
          { num: 3, label: 'Keyframes', path: 'stage-3-keyframes' },
          { num: 4, label: 'Audio', path: 'stage-4-audio' },
          { num: 5, label: 'Video', path: 'stage-5-video' },
          { num: 6, label: 'Assembly & Master', path: '' },
        ].map((s) => (
          <button
            key={s.num}
            type="button"
            onClick={() => router.push(`/studio/${projectId}/${s.path}`)}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg font-semibold transition-colors ${
              s.num === 6
                ? 'bg-zinc-800 text-emerald-400 border border-zinc-700'
                : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900'
            }`}
          >
            <span className="w-5 h-5 rounded-full bg-zinc-900 flex items-center justify-center text-[10px]">
              {s.num}
            </span>
            <span>{s.label}</span>
          </button>
        ))}
      </div>

      {/* Main Two-Column Master Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 mb-12">
        {/* Left Column (2 Cols): Master Video Player */}
        <div className="lg:col-span-2 flex flex-col gap-4">
          <div className="relative aspect-video w-full rounded-2xl overflow-hidden bg-zinc-950 border border-zinc-800 shadow-2xl flex items-center justify-center group">
            {finalVideoUrl ? (
              <video
                src={finalVideoUrl}
                controls
                className="w-full h-full object-cover"
                playsInline
              />
            ) : (
              <div className="flex flex-col items-center justify-center gap-3 p-8 text-center text-zinc-500">
                <Film className="w-12 h-12 text-zinc-700" />
                <p className="text-sm font-semibold text-zinc-400">
                  Master timeline not yet rendered.
                </p>
                <p className="text-xs text-zinc-600 max-w-sm">
                  Click "Assemble Master Video" above to stitch all scene clips, apply sidechain
                  ducking, and render ASS karaoke subtitles.
                </p>
              </div>
            )}
          </div>

          {/* Subtitle & Settings Bar */}
          <div className="flex items-center justify-between p-4 bg-zinc-950 border border-zinc-800 rounded-xl">
            <div className="flex items-center gap-3">
              <label className="flex items-center gap-2 text-xs font-semibold text-zinc-300 cursor-pointer">
                <input
                  type="checkbox"
                  checked={burnCaptions}
                  onChange={(e) => setBurnCaptions(e.target.checked)}
                  className="rounded bg-zinc-900 border-zinc-700 text-emerald-500 focus:ring-0"
                />
                Burn ASS Karaoke Subtitles into Video Stream
              </label>
            </div>

            <span className="text-[11px] text-zinc-500 font-mono">
              Transitions: Cut (0.5s) • Audio: EBU R128 (-14 LUFS)
            </span>
          </div>
        </div>

        {/* Right Column (1 Col): Clickable Poster Thumbnails & Delivery */}
        <div className="flex flex-col gap-6">
          {/* Thumbnail Selection Card */}
          <div className="flex flex-col p-5 bg-zinc-950 border border-zinc-800 rounded-2xl shadow-xl gap-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <ImageIcon className="w-4 h-4 text-emerald-400" />
                <span className="text-xs font-bold uppercase tracking-wider text-zinc-200">
                  YouTube Poster Thumbnail
                </span>
              </div>
              {thumbnail?.status === 'completed' && (
                <span className="text-[10px] font-bold text-emerald-400 px-2 py-0.5 rounded bg-emerald-950/60 border border-emerald-800">
                  Ready
                </span>
              )}
            </div>

            <div className="relative aspect-video rounded-xl overflow-hidden bg-zinc-900 border border-zinc-800 flex items-center justify-center">
              {thumbnail?.selectedAssetUrl ? (
                <img
                  src={thumbnail.selectedAssetUrl}
                  alt="Poster Thumbnail"
                  className="w-full h-full object-cover"
                />
              ) : (
                <span className="text-xs text-zinc-600 italic">Thumbnail not generated yet</span>
              )}
            </div>

            {thumbnail?.variants && thumbnail.variants.length > 0 && (
              <VariantPicker
                variants={thumbnail.variants}
                selectedUrl={thumbnail.selectedAssetUrl || null}
                onSelect={(url) => selectVariant('/assembly/thumbnail/selectedAssetUrl', url)}
              />
            )}
          </div>

          {/* Timeline Breakdown Preview */}
          <div className="flex flex-col p-5 bg-zinc-950 border border-zinc-800 rounded-2xl shadow-xl gap-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Layers className="w-4 h-4 text-sky-400" />
                <span className="text-xs font-bold uppercase tracking-wider text-zinc-200">
                  Timeline Reel ({scenes.length} Scenes)
                </span>
              </div>
            </div>

            <div className="flex flex-col gap-2 max-h-60 overflow-y-auto pr-1">
              {scenes.map((scene) => (
                <div
                  key={scene.id}
                  className="flex items-center justify-between p-2 rounded-lg bg-zinc-900 border border-zinc-800 text-xs"
                >
                  <span className="font-semibold text-zinc-300">Scene #{scene.sceneNumber}</span>
                  <span className="text-zinc-500 font-mono text-[11px]">
                    {scene.timestamp.startSec}s - {scene.timestamp.endSec}s
                  </span>
                  <span
                    className={`text-[10px] px-2 py-0.5 rounded font-mono ${
                      scene.video.status === 'completed'
                        ? 'bg-emerald-950 text-emerald-400'
                        : 'bg-zinc-800 text-zinc-400'
                    }`}
                  >
                    {scene.video.status}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Export Hub Modal */}
      <ExportHubModal
        projectId={projectId}
        isOpen={isExportModalOpen}
        onClose={() => setIsExportModalOpen(false)}
        finalVideoUrl={finalVideoUrl}
        bundleZipUrl={bundleZipUrl}
        onExportZip={handleExportZip}
      />
    </div>
  );
}
