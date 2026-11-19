'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { Database, Film, Sparkles, FolderArchive, Layers, Plus } from 'lucide-react';
import { ContextShelf } from '@/components/context/ContextShelf';
import { UploadDropzone } from '@/components/context/UploadDropzone';
import { ContextArtifactItem } from '@/types/context';

export default function StudioPage() {
  const [projectId] = useState('proj_98a7f');
  const [isShelfOpen, setIsShelfOpen] = useState(false);
  const [recentArtifacts, setRecentArtifacts] = useState<ContextArtifactItem[]>([]);

  const handleArtifactAdded = (art: ContextArtifactItem) => {
    setRecentArtifacts((prev) => [art, ...prev]);
  };

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100 font-sans">
      {/* Studio Topbar */}
      <header className="border-b border-slate-800 bg-slate-900/80 px-6 py-3.5 backdrop-blur-md sticky top-0 z-30">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600 text-white shadow-sm">
              <Film className="h-4 w-4" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-sm font-semibold tracking-tight text-white">The Horizon Signal</h1>
                <span className="rounded-full bg-indigo-950/80 border border-indigo-800 px-2 py-0.5 text-[10px] font-medium text-indigo-300">
                  cinematic_drama
                </span>
                <span className="rounded-full bg-slate-800 px-2 py-0.5 text-[10px] font-mono text-slate-400">
                  ID: {projectId}
                </span>
              </div>
              <p className="text-[11px] text-slate-400">
                1080p • 16:9 • 35mm Anamorphic • Single Source of Truth: PostgreSQL JSONB Manifest
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={() => setIsShelfOpen(true)}
              className="flex items-center gap-1.5 rounded-lg border border-indigo-700 bg-indigo-600/20 px-3.5 py-1.5 text-xs font-medium text-indigo-300 transition-colors hover:bg-indigo-600/30"
            >
              <Database className="h-3.5 w-3.5" />
              Multimodal Context Shelf
              {recentArtifacts.length > 0 && (
                <span className="ml-1 rounded-full bg-indigo-500 px-1.5 py-0.2 text-[10px] text-white">
                  {recentArtifacts.length}
                </span>
              )}
            </button>
          </div>
        </div>
      </header>

      {/* Main Studio Viewport */}
      <div className="mx-auto max-w-6xl p-8 space-y-8">
        {/* Multimodal Context Ingestion Banner */}
        <section className="rounded-2xl border border-slate-800 bg-gradient-to-br from-slate-900 to-indigo-950/30 p-6 shadow-xl">
          <div className="flex flex-col md:flex-row md:items-start justify-between gap-6">
            <div className="max-w-xl">
              <div className="flex items-center gap-2 text-indigo-400 text-xs font-semibold tracking-wide uppercase">
                <Sparkles className="h-3.5 w-3.5" />
                Phase 3: NotebookLM-Style Multimodal Context Layer
              </div>
              <h2 className="mt-1.5 text-lg font-bold text-white">
                Content-Addressed Ingestion Engine
              </h2>
              <p className="mt-2 text-xs leading-relaxed text-slate-300">
                Decode once, reuse everywhere. Reference scripts, PDFs, pitch decks, web articles, and video footage are hashed with <strong>SHA-256</strong>, persisted to S3/R2 storage, and analyzed via <strong>Gemini Flash</strong> into production bibles for characters, keyframes, and audio.
              </p>
            </div>

            <div className="w-full md:w-96">
              <UploadDropzone
                projectId={projectId}
                onArtifactUploaded={handleArtifactAdded}
              />
            </div>
          </div>
        </section>

        {/* Studio Pipeline Stages Preview */}
        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              CineForge 7-Stage Production Pipeline
            </h3>
            <span className="text-xs text-slate-500">Master JSON Manifest v1</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <Link
              href={`/studio/${projectId}/stage-1-planner`}
              className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 hover:border-indigo-500/60 transition-colors block"
            >
              <div className="flex items-center justify-between text-xs text-slate-400">
                <span>Stage 1</span>
                <span className="rounded-full bg-slate-800 px-2 py-0.5 text-[10px]">Ready</span>
              </div>
              <h4 className="mt-2 text-sm font-semibold text-white">Planner Section</h4>
              <p className="mt-1 text-xs text-slate-400">Context-aware structured generation</p>
            </Link>

            <Link
              href={`/studio/${projectId}/stage-2-consistencies`}
              className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 hover:border-indigo-500/60 transition-colors block"
            >
              <div className="flex items-center justify-between text-xs text-slate-400">
                <span>Stage 2</span>
                <span className="rounded-full bg-slate-800 px-2 py-0.5 text-[10px]">Ready</span>
              </div>
              <h4 className="mt-2 text-sm font-semibold text-white">Characters & 360°</h4>
              <p className="mt-1 text-xs text-slate-400">Consistent turnaround sheets</p>
            </Link>

            <Link
              href={`/studio/${projectId}/stage-3-keyframes`}
              className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 hover:border-indigo-500/60 transition-colors block"
            >
              <div className="flex items-center justify-between text-xs text-slate-400">
                <span>Stage 3</span>
                <span className="rounded-full bg-slate-800 px-2 py-0.5 text-[10px]">Ready</span>
              </div>
              <h4 className="mt-2 text-sm font-semibold text-white">Keyframes</h4>
              <p className="mt-1 text-xs text-slate-400">Reference-injected anchor frames</p>
            </Link>

            <Link
              href={`/studio/${projectId}`}
              className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 hover:border-indigo-500/60 transition-colors block"
            >
              <div className="flex items-center justify-between text-xs text-slate-400">
                <span>Stage 4-7</span>
                <span className="rounded-full bg-slate-800 px-2 py-0.5 text-[10px]">Queued</span>
              </div>
              <h4 className="mt-2 text-sm font-semibold text-white">Audio & Assembly</h4>
              <p className="mt-1 text-xs text-slate-400">FFmpeg 7 sync & Loudnorm</p>
            </Link>
          </div>
        </section>
      </div>

      {/* Slide-over Context Shelf Drawer */}
      <ContextShelf
        projectId={projectId}
        isOpen={isShelfOpen}
        onToggle={() => setIsShelfOpen(!isShelfOpen)}
      />
    </main>
  );
}
